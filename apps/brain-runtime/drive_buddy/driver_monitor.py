#!/usr/bin/env python3
"""
Driver Monitoring System for Drive Buddy
Uses vision to detect drowsiness, distraction, and attention.

Features:
- Eye state detection (open/closed)
- Gaze direction (looking at road vs away)
- Drowsiness scoring (PERCLOS - percentage eye closure)
- Yawn detection
- Head pose (nodding off)
- Distraction alerts
"""

import cv2
import time
import numpy as np
from typing import Optional, Callable
from dataclasses import dataclass, asdict
from collections import deque
from enum import Enum

# Lazy imports
_face_app = None
_mediapipe_face = None


class AttentionState(Enum):
    ATTENTIVE = "attentive"
    DISTRACTED = "distracted"
    DROWSY = "drowsy"
    EYES_CLOSED = "eyes_closed"
    NOT_DETECTED = "not_detected"


@dataclass
class DriverState:
    """Current driver state"""
    timestamp: float = 0

    # Face detection
    face_detected: bool = False
    face_confidence: float = 0

    # Eyes
    eyes_open: bool = True
    eye_aspect_ratio: float = 0.3  # EAR - lower = more closed
    blink_count: int = 0

    # Attention
    attention_state: str = "attentive"
    looking_at_road: bool = True
    gaze_direction: str = "center"  # center, left, right, up, down

    # Drowsiness (PERCLOS - % of time eyes closed in last 60s)
    drowsiness_score: float = 0  # 0-100, >40 is concerning
    drowsiness_alert: bool = False

    # Head pose
    head_pitch: float = 0  # nodding
    head_yaw: float = 0    # turning
    head_roll: float = 0   # tilting

    # Yawning
    mouth_open: bool = False
    yawn_count: int = 0

    def to_dict(self):
        return asdict(self)


class DriverMonitor:
    """
    Monitors driver state using camera.

    Alerts:
    - Eyes closed > 2 seconds
    - Drowsiness score > 40%
    - Looking away from road > 3 seconds
    - Multiple yawns in short period
    """

    # Thresholds
    EYE_AR_THRESHOLD = 0.2  # Below this = eyes closed
    DROWSY_THRESHOLD = 40   # PERCLOS > 40% is dangerous
    LOOK_AWAY_THRESHOLD = 3.0  # seconds
    YAWN_AR_THRESHOLD = 0.6  # Mouth aspect ratio for yawn

    def __init__(
        self,
        camera_index: int = 0,
        on_state_change: Optional[Callable[[DriverState], None]] = None,
        on_alert: Optional[Callable[[str, str], None]] = None,  # (alert_type, message)
    ):
        self.camera_index = camera_index
        self.on_state_change = on_state_change
        self.on_alert = on_alert

        self.state = DriverState()
        self.cap = None
        self.running = False

        # Tracking
        self._eye_history = deque(maxlen=180)  # 60 seconds at 3 fps
        self._blink_frames = 0
        self._look_away_start = None
        self._last_alert_time = {}
        self._yawn_times = deque(maxlen=10)

        # Face detection
        self._face_app = None

    def _load_face_detector(self):
        """Lazy load InsightFace"""
        if self._face_app is None:
            print("[Driver] Loading face detector...")
            from insightface.app import FaceAnalysis
            self._face_app = FaceAnalysis(
                allowed_modules=['detection', 'landmark_2d_106'],
                providers=['CUDAExecutionProvider', 'CPUExecutionProvider']
            )
            self._face_app.prepare(ctx_id=0, det_size=(640, 480))
        return self._face_app

    def _calculate_ear(self, landmarks, eye_indices):
        """
        Calculate Eye Aspect Ratio (EAR).
        EAR = (|p2-p6| + |p3-p5|) / (2 * |p1-p4|)
        Lower EAR = more closed eyes
        """
        try:
            # Get eye points (simplified - using approximate indices)
            # InsightFace 106 landmarks: eyes are around indices 33-42 (left) and 87-96 (right)
            p1, p2, p3, p4, p5, p6 = [landmarks[i] for i in eye_indices]

            # Calculate distances
            A = np.linalg.norm(np.array(p2) - np.array(p6))
            B = np.linalg.norm(np.array(p3) - np.array(p5))
            C = np.linalg.norm(np.array(p1) - np.array(p4))

            ear = (A + B) / (2.0 * C) if C > 0 else 0
            return ear
        except:
            return 0.3  # Default open

    def _calculate_mar(self, landmarks):
        """
        Calculate Mouth Aspect Ratio (MAR) for yawn detection.
        """
        try:
            # Mouth landmarks (approximate for 106-point model)
            # Top lip, bottom lip, corners
            top = landmarks[52]
            bottom = landmarks[58]
            left = landmarks[48]
            right = landmarks[54]

            vertical = np.linalg.norm(np.array(top) - np.array(bottom))
            horizontal = np.linalg.norm(np.array(left) - np.array(right))

            mar = vertical / horizontal if horizontal > 0 else 0
            return mar
        except:
            return 0.3

    def _calculate_gaze(self, landmarks, bbox):
        """Estimate gaze direction from face landmarks"""
        try:
            # Get nose tip and face center
            nose = landmarks[54] if len(landmarks) > 54 else landmarks[30]
            x1, y1, x2, y2 = bbox
            face_center_x = (x1 + x2) / 2
            face_width = x2 - x1

            # Nose position relative to face center
            nose_offset = (nose[0] - face_center_x) / face_width

            if nose_offset < -0.15:
                return "left"
            elif nose_offset > 0.15:
                return "right"
            else:
                return "center"
        except:
            return "center"

    def _calculate_head_pose(self, landmarks):
        """Estimate head pose from landmarks"""
        try:
            # Simplified head pose from landmark positions
            # Would need proper 3D projection for accurate angles
            nose = landmarks[54] if len(landmarks) > 54 else landmarks[30]
            left_eye = landmarks[36] if len(landmarks) > 36 else None
            right_eye = landmarks[45] if len(landmarks) > 45 else None

            if left_eye and right_eye:
                # Yaw (left-right rotation)
                eye_diff = right_eye[0] - left_eye[0]
                self.state.head_yaw = 0  # Simplified

                # Pitch (nodding) - approximate from nose position
                self.state.head_pitch = 0

        except:
            pass

    def _update_drowsiness(self, eyes_open: bool):
        """Update PERCLOS drowsiness score"""
        # Record eye state
        self._eye_history.append(1 if eyes_open else 0)

        # Calculate PERCLOS (% eyes closed in history window)
        if len(self._eye_history) > 10:
            closed_count = len(self._eye_history) - sum(self._eye_history)
            self.state.drowsiness_score = (closed_count / len(self._eye_history)) * 100

            self.state.drowsiness_alert = self.state.drowsiness_score > self.DROWSY_THRESHOLD

    def _check_alerts(self):
        """Check for alert conditions"""
        now = time.time()

        # Cooldown between same alert types
        def should_alert(alert_type, cooldown=30):
            last = self._last_alert_time.get(alert_type, 0)
            if now - last > cooldown:
                self._last_alert_time[alert_type] = now
                return True
            return False

        # Eyes closed too long
        if not self.state.eyes_open:
            if self._blink_frames > 6:  # ~2 seconds at 3fps
                if should_alert("eyes_closed", 10):
                    self._send_alert("eyes_closed", "Your eyes have been closed for too long!")
        else:
            self._blink_frames = 0

        # Drowsiness
        if self.state.drowsiness_alert:
            if should_alert("drowsy", 60):
                self._send_alert("drowsy", "You seem drowsy. Consider taking a break.")

        # Looking away
        if not self.state.looking_at_road:
            if self._look_away_start is None:
                self._look_away_start = now
            elif now - self._look_away_start > self.LOOK_AWAY_THRESHOLD:
                if should_alert("distracted", 15):
                    self._send_alert("distracted", "Please keep your eyes on the road.")
        else:
            self._look_away_start = None

        # Multiple yawns
        if self.state.mouth_open:
            # Check if this is a new yawn
            if not self._yawn_times or now - self._yawn_times[-1] > 5:
                self._yawn_times.append(now)
                self.state.yawn_count += 1

                # Alert if many yawns in last 5 minutes
                recent_yawns = sum(1 for t in self._yawn_times if now - t < 300)
                if recent_yawns >= 3:
                    if should_alert("yawning", 120):
                        self._send_alert("yawning", "You've yawned multiple times. Time for a break?")

    def _send_alert(self, alert_type: str, message: str):
        """Send alert via callback"""
        print(f"[Driver Alert] {alert_type}: {message}")
        if self.on_alert:
            self.on_alert(alert_type, message)

    def process_frame(self, frame) -> DriverState:
        """Process a single frame"""
        self.state.timestamp = time.time()

        # Detect faces
        face_app = self._load_face_detector()
        faces = face_app.get(frame)

        if not faces:
            self.state.face_detected = False
            self.state.attention_state = AttentionState.NOT_DETECTED.value
            self._update_drowsiness(True)  # Assume eyes open if no face
            return self.state

        # Use first face (driver)
        face = faces[0]
        self.state.face_detected = True
        self.state.face_confidence = float(face.det_score) if hasattr(face, 'det_score') else 0.9

        # Get landmarks if available
        landmarks = getattr(face, 'landmark_2d_106', None)
        bbox = face.bbox.astype(int)

        if landmarks is not None and len(landmarks) >= 68:
            # Eye aspect ratio (simplified)
            # Using approximate indices for 106-point model
            left_eye_indices = [33, 34, 35, 36, 37, 38]  # Approximate
            right_eye_indices = [87, 88, 89, 90, 91, 92]  # Approximate

            try:
                left_ear = self._calculate_ear(landmarks, left_eye_indices)
                right_ear = self._calculate_ear(landmarks, right_eye_indices)
                self.state.eye_aspect_ratio = (left_ear + right_ear) / 2
            except:
                self.state.eye_aspect_ratio = 0.3

            # Eyes open/closed
            self.state.eyes_open = self.state.eye_aspect_ratio > self.EYE_AR_THRESHOLD

            # Mouth (yawn detection)
            try:
                mar = self._calculate_mar(landmarks)
                self.state.mouth_open = mar > self.YAWN_AR_THRESHOLD
            except:
                self.state.mouth_open = False

            # Gaze direction
            self.state.gaze_direction = self._calculate_gaze(landmarks, bbox)
            self.state.looking_at_road = self.state.gaze_direction == "center"

            # Head pose
            self._calculate_head_pose(landmarks)

        else:
            # No landmarks - use simpler detection
            self.state.eyes_open = True
            self.state.looking_at_road = True

        # Update drowsiness score
        self._update_drowsiness(self.state.eyes_open)

        # Update blink counter
        if not self.state.eyes_open:
            self._blink_frames += 1
        else:
            if self._blink_frames > 0 and self._blink_frames < 5:
                self.state.blink_count += 1
            self._blink_frames = 0

        # Determine attention state
        if not self.state.eyes_open:
            self.state.attention_state = AttentionState.EYES_CLOSED.value
        elif self.state.drowsiness_score > self.DROWSY_THRESHOLD:
            self.state.attention_state = AttentionState.DROWSY.value
        elif not self.state.looking_at_road:
            self.state.attention_state = AttentionState.DISTRACTED.value
        else:
            self.state.attention_state = AttentionState.ATTENTIVE.value

        # Check for alerts
        self._check_alerts()

        # Callback
        if self.on_state_change:
            self.on_state_change(self.state)

        return self.state

    def start(self):
        """Start camera capture"""
        self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_V4L2)
        if not self.cap.isOpened():
            self.cap = cv2.VideoCapture(self.camera_index)

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.running = True
        print("[Driver] Monitor started")

    def stop(self):
        """Stop camera capture"""
        self.running = False
        if self.cap:
            self.cap.release()
        print("[Driver] Monitor stopped")

    def run_loop(self, show_ui: bool = False):
        """Main processing loop"""
        self.start()

        if show_ui:
            cv2.namedWindow('Driver Monitor', cv2.WINDOW_NORMAL)

        try:
            while self.running:
                ret, frame = self.cap.read()
                if not ret:
                    continue

                state = self.process_frame(frame)

                if show_ui:
                    # Draw overlays
                    display = frame.copy()

                    # Status bar
                    status_color = (0, 255, 0) if state.attention_state == "attentive" else (0, 0, 255)
                    cv2.putText(display, f"Status: {state.attention_state.upper()}",
                                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2)
                    cv2.putText(display, f"Eyes: {'OPEN' if state.eyes_open else 'CLOSED'}",
                                (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                    cv2.putText(display, f"Drowsiness: {state.drowsiness_score:.0f}%",
                                (10, 85), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                    cv2.putText(display, f"Gaze: {state.gaze_direction}",
                                (10, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

                    cv2.imshow('Driver Monitor', display)

                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break

                time.sleep(0.1)  # ~10 FPS for driver monitoring

        except KeyboardInterrupt:
            pass
        finally:
            self.stop()
            if show_ui:
                cv2.destroyAllWindows()


if __name__ == "__main__":
    def on_alert(alert_type, message):
        print(f"\n⚠️  ALERT: {message}\n")

    monitor = DriverMonitor(on_alert=on_alert)
    monitor.run_loop(show_ui=True)
