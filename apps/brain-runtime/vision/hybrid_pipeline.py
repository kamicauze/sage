#!/usr/bin/env python3
"""
Hybrid Vision Pipeline for Sage
- InsightFace: Continuous fast detection (~20ms) at 15-30 FPS
- YOLO: Object detection for context (coffee cup, phone, etc.)
- VLM: Triggered every 60s or on significant change (~2-3s)

This is sustainable 24/7 without thermal throttling.
"""

import cv2
import time
import json
import base64
import hashlib
import asyncio
import numpy as np
from typing import Optional, Dict, Any, Callable, List
from dataclasses import dataclass, asdict, field
from enum import Enum
import threading
import queue

# Lazy imports to speed up startup
_face_app = None
_deepface = None
_yolo_model = None


class VLMTrigger(Enum):
    TIMER = "timer"
    SCENE_CHANGE = "scene_change"
    PERSON_APPEARED = "person_appeared"
    PERSON_LEFT = "person_left"
    USER_REQUEST = "user_request"
    EMOTION_CHANGE = "emotion_change"


@dataclass
class DetectedObject:
    """A detected object from YOLO"""
    label: str
    confidence: float
    bbox: List[int]  # [x1, y1, x2, y2]

    def to_dict(self):
        return asdict(self)


@dataclass
class FastResult:
    """Result from fast path (InsightFace + YOLO) - runs every frame"""
    timestamp: float
    face_detected: bool
    people_count: int
    faces: list  # [{bbox, age, gender, confidence, emotion}]
    objects: list  # [DetectedObject] - detected objects
    latency_ms: float


@dataclass
class VLMResult:
    """Result from slow path (VLM) - runs periodically"""
    timestamp: float
    trigger: str
    description: str
    activity: str
    mood: str
    objects: list
    latency_ms: float


@dataclass
class VisionState:
    """Combined vision state for Sage brain"""
    # Fast path (always fresh)
    face_detected: bool = False
    people_count: int = 0
    primary_emotion: str = "unknown"
    attention: str = "unknown"  # "looking_at_camera", "looking_away", "eyes_closed"

    # Object detection (YOLO)
    detected_objects: List[str] = field(default_factory=list)  # ["coffee_cup", "phone", "book"]
    object_count: int = 0

    # Slow path (updated periodically)
    scene_description: str = ""
    activity: str = "unknown"
    last_vlm_update: float = 0

    def to_dict(self):
        return asdict(self)


class HybridVisionPipeline:
    """
    Hybrid approach:
    - Fast path: InsightFace runs on every frame (~20ms)
    - Slow path: VLM runs every 60s or on trigger (~2-3s)
    """

    def __init__(
        self,
        camera_index: int = 0,
        vlm_interval: float = 60.0,
        vlm_provider: str = "ollama",  # "ollama" or "local"
        vlm_model: str = "moondream",
        ollama_host: str = "http://localhost:11434",
        enable_vlm: bool = True,
        enable_emotion: bool = True,
        enable_yolo: bool = True,
        yolo_model: str = "yolov8n",  # nano model for speed
        yolo_interval: int = 5,  # Run YOLO every N frames
        on_state_change: Optional[Callable[[VisionState], None]] = None,
        on_vlm_result: Optional[Callable[[VLMResult], None]] = None,
    ):
        self.camera_index = camera_index
        self.vlm_interval = vlm_interval
        self.vlm_provider = vlm_provider
        self.vlm_model = vlm_model
        self.ollama_host = ollama_host
        self.enable_vlm = enable_vlm
        self.enable_emotion = enable_emotion
        self.enable_yolo = enable_yolo
        self.yolo_model_name = yolo_model
        self.yolo_interval = yolo_interval
        self.on_state_change = on_state_change
        self.on_vlm_result = on_vlm_result

        # State
        self.state = VisionState()
        self.last_vlm_time = 0
        self.last_scene_hash = None
        self.had_person = False
        self.last_emotion = "neutral"
        self.start_time = time.time()

        # Threading
        self.running = False
        self.vlm_queue = queue.Queue()
        self.vlm_thread = None

        # Models (lazy loaded)
        self._face_app = None
        self._deepface_loaded = False
        self._yolo_model = None
        self._last_objects = []  # Cache detected objects

        # Context-relevant YOLO classes (subset of COCO for efficiency)
        # Full list: https://docs.ultralytics.com/datasets/detect/coco/
        self._relevant_classes = {
            # Personal items
            39: "bottle", 41: "cup", 73: "laptop", 74: "mouse",
            75: "remote", 76: "keyboard", 67: "cell phone", 66: "keyboard",
            # Reading/work
            84: "book", 85: "clock",
            # Food/drink
            46: "banana", 47: "apple", 48: "sandwich", 49: "orange",
            50: "broccoli", 51: "carrot", 52: "hot dog", 53: "pizza",
            54: "donut", 55: "cake", 40: "wine glass", 42: "fork",
            43: "knife", 44: "spoon", 45: "bowl",
            # Accessories
            27: "backpack", 28: "umbrella", 26: "handbag", 30: "suitcase",
            # Entertainment
            32: "sports ball", 72: "tv",
            # Animals (pets)
            16: "cat", 17: "dog",
        }

        # Camera
        self.cap = None
        self.frame_count = 0

        # Frame buffer for temporal/motion context (video-like VLM)
        self.frame_buffer = []
        self.frame_buffer_size = 8  # ~0.5s at 15fps
        self.frame_buffer_interval = 3  # Store every Nth frame

    def _load_face_detector(self):
        """Lazy load InsightFace"""
        if self._face_app is None:
            print("[Vision] Loading InsightFace...")
            from insightface.app import FaceAnalysis
            self._face_app = FaceAnalysis(
                allowed_modules=['detection', 'genderage'],
                providers=['CUDAExecutionProvider', 'CPUExecutionProvider']
            )
            self._face_app.prepare(ctx_id=0, det_size=(640, 480))
            print("[Vision] InsightFace ready")
        return self._face_app

    def _load_yolo(self):
        """Lazy load YOLO model"""
        if self._yolo_model is None and self.enable_yolo:
            print("[Vision] Loading YOLO...")
            try:
                from ultralytics import YOLO
                # Use nano model for speed (~5-10ms on GPU)
                self._yolo_model = YOLO(f"{self.yolo_model_name}.pt")
                print(f"[Vision] YOLO {self.yolo_model_name} ready")
            except ImportError:
                print("[Vision] YOLO not available. Install: pip install ultralytics")
                self.enable_yolo = False
            except Exception as e:
                print(f"[Vision] YOLO load error: {e}")
                self.enable_yolo = False
        return self._yolo_model

    def _detect_objects(self, frame) -> List[DetectedObject]:
        """Run YOLO object detection"""
        if not self.enable_yolo:
            return self._last_objects

        model = self._load_yolo()
        if model is None:
            return self._last_objects

        try:
            # Run inference with filtering
            results = model(
                frame,
                verbose=False,
                conf=0.4,  # Confidence threshold
                classes=list(self._relevant_classes.keys())  # Only relevant classes
            )

            objects = []
            if results and len(results) > 0:
                for box in results[0].boxes:
                    cls_id = int(box.cls[0])
                    if cls_id in self._relevant_classes:
                        label = self._relevant_classes[cls_id]
                        conf = float(box.conf[0])
                        bbox = box.xyxy[0].cpu().numpy().astype(int).tolist()
                        objects.append(DetectedObject(
                            label=label,
                            confidence=conf,
                            bbox=bbox
                        ))

            self._last_objects = objects
            return objects

        except Exception as e:
            print(f"[Vision] YOLO error: {e}")
            return self._last_objects

    def _get_emotion(self, frame, bbox) -> str:
        """Get emotion using DeepFace (only when enabled)"""
        if not self.enable_emotion:
            return "unknown"

        try:
            x1, y1, x2, y2 = bbox
            face_crop = frame[y1:y2, x1:x2]
            if face_crop.size == 0 or min(face_crop.shape[:2]) < 30:
                return "unknown"

            from deepface import DeepFace
            result = DeepFace.analyze(
                face_crop,
                actions=['emotion'],
                detector_backend='skip',
                enforce_detection=False,
                silent=True
            )
            if result:
                emotion = result[0].get('dominant_emotion', 'unknown')
                print(f"[Vision] DeepFace emotion: {emotion}")
                return emotion
        except Exception as e:
            print(f"[Vision] DeepFace error: {e}")
        return "unknown"

    def _preprocess_frame(self, frame):
        """CLAHE preprocessing for better skin tone handling"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        equalized = clahe.apply(gray)
        return cv2.cvtColor(equalized, cv2.COLOR_GRAY2BGR)

    def _compute_scene_hash(self, frame) -> str:
        """Compute a simple hash to detect scene changes"""
        # Downsample and convert to grayscale
        small = cv2.resize(frame, (32, 32))
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        # Compute hash
        return hashlib.md5(gray.tobytes()).hexdigest()[:8]

    def _scene_changed(self, new_hash) -> bool:
        """Check if scene changed significantly"""
        if self.last_scene_hash is None:
            self.last_scene_hash = new_hash
            return False
        changed = new_hash != self.last_scene_hash
        self.last_scene_hash = new_hash
        return changed

    def _add_to_frame_buffer(self, frame):
        """Add frame to buffer for temporal context"""
        if self.frame_count % self.frame_buffer_interval == 0:
            # Resize for efficiency
            small = cv2.resize(frame, (320, 240))
            self.frame_buffer.append(small)
            if len(self.frame_buffer) > self.frame_buffer_size:
                self.frame_buffer.pop(0)

    def _create_frame_grid(self) -> Optional[np.ndarray]:
        """Create a 2x4 grid of buffered frames for temporal context"""
        if len(self.frame_buffer) < 4:
            return None

        # Take evenly spaced frames from buffer
        indices = np.linspace(0, len(self.frame_buffer) - 1, 8, dtype=int)
        frames = [self.frame_buffer[i] for i in indices if i < len(self.frame_buffer)]

        # Pad if needed
        while len(frames) < 8:
            frames.append(frames[-1] if frames else np.zeros((240, 320, 3), dtype=np.uint8))

        # Create 2x4 grid (2 rows, 4 columns)
        row1 = np.hstack(frames[:4])
        row2 = np.hstack(frames[4:8])
        grid = np.vstack([row1, row2])

        return grid

    def _should_run_vlm(self, frame, fast_result: FastResult) -> Optional[VLMTrigger]:
        """Determine if VLM should run and why"""
        if not self.enable_vlm:
            return None

        now = time.time()

        # 1. Person appeared (was absent, now present) - high priority
        if fast_result.face_detected and not self.had_person:
            print("[Vision] VLM trigger: Person appeared")
            return VLMTrigger.PERSON_APPEARED

        # 2. Person left (was present, now absent)
        if not fast_result.face_detected and self.had_person:
            print("[Vision] VLM trigger: Person left")
            return VLMTrigger.PERSON_LEFT

        # 3. Initial scan - run VLM shortly after startup if person detected (only once)
        if fast_result.face_detected and self.last_vlm_time == 0 and (now - self.start_time) > 3:
            # Mark that we've triggered the initial scan to prevent spam
            self.last_vlm_time = now
            print("[Vision] VLM trigger: Initial scan")
            return VLMTrigger.TIMER

        # 4. Time-based: Every N seconds
        if now - self.last_vlm_time > self.vlm_interval:
            print(f"[Vision] VLM trigger: Timer ({self.vlm_interval}s interval)")
            return VLMTrigger.TIMER

        # 5. Significant emotion change
        if fast_result.faces:
            current_emotion = fast_result.faces[0].get('emotion', 'neutral')
            if current_emotion != self.last_emotion and current_emotion in ['angry', 'sad', 'fear']:
                print(f"[Vision] VLM trigger: Emotion change to {current_emotion}")
                return VLMTrigger.EMOTION_CHANGE

        # 6. Scene change (optional, can be noisy)
        # scene_hash = self._compute_scene_hash(frame)
        # if self._scene_changed(scene_hash):
        #     return VLMTrigger.SCENE_CHANGE

        return None

    def _run_vlm_ollama(self, frame, trigger: VLMTrigger) -> VLMResult:
        """Run VLM via Ollama API"""
        import requests

        start = time.time()

        # Encode frame to base64
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        img_base64 = base64.b64encode(buffer).decode('utf-8')

        # Craft prompt based on trigger
        if trigger == VLMTrigger.PERSON_APPEARED:
            prompt = "A person just appeared. Briefly describe who you see and what they seem to be doing. Be concise (1-2 sentences)."
        elif trigger == VLMTrigger.PERSON_LEFT:
            prompt = "The person left. Briefly describe the empty scene. (1 sentence)"
        elif trigger == VLMTrigger.EMOTION_CHANGE:
            prompt = "The person's mood seems to have changed. Describe their current emotional state and body language. (1-2 sentences)"
        else:
            prompt = "Briefly describe: 1) Who is in the scene 2) What they're doing 3) Their apparent mood. Be concise (2-3 sentences max)."

        try:
            response = requests.post(
                f"{self.ollama_host}/api/generate",
                json={
                    "model": self.vlm_model,
                    "prompt": prompt,
                    "images": [img_base64],
                    "stream": False,
                    "options": {"num_predict": 100}
                },
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                description = result.get('response', '').strip()

                # Parse out activity and mood (simple heuristics)
                activity = "unknown"
                mood = "unknown"

                desc_lower = description.lower()
                if any(w in desc_lower for w in ['working', 'typing', 'computer', 'desk']):
                    activity = "working"
                elif any(w in desc_lower for w in ['reading', 'book']):
                    activity = "reading"
                elif any(w in desc_lower for w in ['relaxing', 'resting', 'couch', 'sitting']):
                    activity = "relaxing"
                elif any(w in desc_lower for w in ['eating', 'drinking', 'coffee']):
                    activity = "eating"
                elif any(w in desc_lower for w in ['phone', 'mobile']):
                    activity = "on_phone"

                if any(w in desc_lower for w in ['happy', 'smiling', 'cheerful']):
                    mood = "happy"
                elif any(w in desc_lower for w in ['focused', 'concentrated', 'serious']):
                    mood = "focused"
                elif any(w in desc_lower for w in ['tired', 'exhausted', 'sleepy']):
                    mood = "tired"
                elif any(w in desc_lower for w in ['frustrated', 'annoyed', 'angry']):
                    mood = "frustrated"
                elif any(w in desc_lower for w in ['sad', 'down', 'upset']):
                    mood = "sad"
                elif any(w in desc_lower for w in ['relaxed', 'calm']):
                    mood = "relaxed"

                latency = (time.time() - start) * 1000

                return VLMResult(
                    timestamp=time.time(),
                    trigger=trigger.value,
                    description=description,
                    activity=activity,
                    mood=mood,
                    objects=[],
                    latency_ms=latency
                )
        except Exception as e:
            print(f"[Vision] VLM error: {e}")

        return VLMResult(
            timestamp=time.time(),
            trigger=trigger.value,
            description="VLM unavailable",
            activity="unknown",
            mood="unknown",
            objects=[],
            latency_ms=(time.time() - start) * 1000
        )

    def _vlm_worker(self):
        """Background thread for VLM processing"""
        while self.running:
            try:
                item = self.vlm_queue.get(timeout=1.0)
                if item is None:
                    break

                frame, trigger = item
                result = self._run_vlm_ollama(frame, trigger)

                # Update state
                self.state.scene_description = result.description
                self.state.activity = result.activity
                self.state.last_vlm_update = result.timestamp
                self.last_vlm_time = time.time()

                # Callback
                if self.on_vlm_result:
                    self.on_vlm_result(result)

                print(f"[Vision] VLM ({trigger.value}): {result.description[:80]}... [{result.latency_ms:.0f}ms]")

            except queue.Empty:
                continue
            except Exception as e:
                print(f"[Vision] VLM worker error: {e}")

    def process_frame(self, frame) -> FastResult:
        """
        Process a single frame through the fast path.
        VLM is triggered asynchronously if needed.
        """
        start = time.time()

        # Preprocess for better skin tone handling
        processed = self._preprocess_frame(frame)

        # Fast path: InsightFace
        face_app = self._load_face_detector()
        faces_raw = face_app.get(processed)

        faces = []
        for face in faces_raw:
            bbox = face.bbox.astype(int).tolist()
            x1, y1, x2, y2 = bbox
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(frame.shape[1], x2), min(frame.shape[0], y2)

            # Get emotion every 10 frames to save compute
            # Preserve last known emotion between detection cycles
            emotion = self.last_emotion if self.last_emotion != "neutral" else "unknown"
            if self.enable_emotion and self.frame_count % 10 == 0:
                detected_emotion = self._get_emotion(frame, (x1, y1, x2, y2))
                if detected_emotion != "unknown":
                    emotion = detected_emotion
                    self.last_emotion = emotion

            faces.append({
                'bbox': [x1, y1, x2, y2],
                'age': int(getattr(face, 'age', 0)),
                'gender': 'male' if getattr(face, 'gender', None) == 1 else 'female',
                'confidence': float(face.det_score) if hasattr(face, 'det_score') else 0,
                'emotion': emotion
            })

        # Object detection: Run YOLO every N frames
        objects = []
        if self.enable_yolo and self.frame_count % self.yolo_interval == 0:
            objects = self._detect_objects(frame)
        else:
            objects = self._last_objects  # Use cached results

        latency = (time.time() - start) * 1000

        result = FastResult(
            timestamp=time.time(),
            face_detected=len(faces) > 0,
            people_count=len(faces),
            faces=faces,
            objects=[o.to_dict() if hasattr(o, 'to_dict') else o for o in objects],
            latency_ms=latency
        )

        # Update state
        self.state.face_detected = result.face_detected
        self.state.people_count = result.people_count
        if faces:
            self.state.primary_emotion = faces[0].get('emotion', 'unknown')

        # Update object state
        self.state.detected_objects = list(set(o.label if hasattr(o, 'label') else o.get('label', '') for o in objects))
        self.state.object_count = len(objects)

        # Check if VLM should run
        trigger = self._should_run_vlm(frame, result)
        if trigger and self.vlm_queue.qsize() < 2:  # Don't queue too many
            self.vlm_queue.put((frame.copy(), trigger))

        # Update tracking
        self.had_person = result.face_detected
        self.frame_count += 1

        # Callback
        if self.on_state_change:
            self.on_state_change(self.state)

        return result

    def request_vlm(self, frame=None):
        """Manually request VLM analysis (e.g., user asks 'what do you see?')"""
        if frame is None and self.cap is not None:
            ret, frame = self.cap.read()
            if not ret:
                return
        if frame is not None:
            self.vlm_queue.put((frame.copy(), VLMTrigger.USER_REQUEST))

    def start(self):
        """Start the vision pipeline"""
        self.running = True

        # Open camera
        self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_V4L2)
        if not self.cap.isOpened():
            self.cap = cv2.VideoCapture(self.camera_index)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        # Start VLM worker thread
        if self.enable_vlm:
            self.vlm_thread = threading.Thread(target=self._vlm_worker, daemon=True)
            self.vlm_thread.start()

        print("[Vision] Pipeline started")

    def stop(self):
        """Stop the vision pipeline"""
        self.running = False
        if self.vlm_queue:
            self.vlm_queue.put(None)
        if self.cap:
            self.cap.release()
        print("[Vision] Pipeline stopped")

    def run_loop(self, show_ui: bool = False):
        """Run the main processing loop"""
        self.start()

        if show_ui:
            cv2.namedWindow('Sage Vision', cv2.WINDOW_NORMAL)

        try:
            while self.running:
                ret, frame = self.cap.read()
                if not ret:
                    continue

                result = self.process_frame(frame)

                if show_ui:
                    display = frame.copy()

                    # Draw faces
                    for face in result.faces:
                        x1, y1, x2, y2 = face['bbox']
                        cv2.rectangle(display, (x1, y1), (x2, y2), (0, 255, 0), 2)
                        label = f"{face['gender']}, {face['age']}y, {face['emotion']}"
                        cv2.putText(display, label, (x1, y1-10),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

                    # Draw detected objects
                    for obj in result.objects:
                        if isinstance(obj, dict):
                            x1, y1, x2, y2 = obj['bbox']
                            label = obj['label']
                            conf = obj['confidence']
                        else:
                            x1, y1, x2, y2 = obj.bbox
                            label = obj.label
                            conf = obj.confidence
                        cv2.rectangle(display, (x1, y1), (x2, y2), (255, 165, 0), 2)  # Orange
                        cv2.putText(display, f"{label} {conf:.0%}", (x1, y1-5),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 165, 0), 1)

                    # Draw stats
                    stats = f"Fast: {result.latency_ms:.0f}ms | Objects: {len(result.objects)} | VLM: {self.state.activity}"
                    cv2.putText(display, stats, (10, 25),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

                    # Show detected object names
                    obj_names = ", ".join(self.state.detected_objects[:5])
                    cv2.putText(display, f"Detected: {obj_names}", (10, 50),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 165, 0), 1)

                    cv2.putText(display, self.state.scene_description[:60], (10, 75),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)

                    cv2.imshow('Sage Vision', display)

                    key = cv2.waitKey(1) & 0xFF
                    if key == ord('q'):
                        break
                    elif key == ord('v'):
                        self.request_vlm(frame)

                time.sleep(0.03)  # ~30 FPS

        except KeyboardInterrupt:
            pass
        finally:
            self.stop()
            if show_ui:
                cv2.destroyAllWindows()


# Standalone test
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--no-vlm', action='store_true', help='Disable VLM')
    parser.add_argument('--no-emotion', action='store_true', help='Disable emotion detection')
    parser.add_argument('--no-yolo', action='store_true', help='Disable YOLO object detection')
    parser.add_argument('--vlm-interval', type=float, default=60, help='VLM interval in seconds')
    parser.add_argument('--vlm-model', type=str, default='moondream', help='VLM model name')
    parser.add_argument('--yolo-model', type=str, default='yolov8n', help='YOLO model (yolov8n, yolov8s, yolov8m)')
    parser.add_argument('--yolo-interval', type=int, default=5, help='Run YOLO every N frames')
    parser.add_argument('--no-ui', action='store_true', help='Run without UI')
    args = parser.parse_args()

    def on_state_change(state):
        if state.face_detected or state.object_count > 0:
            objs = ", ".join(state.detected_objects[:3]) if state.detected_objects else "none"
            print(f"[State] Face: {state.people_count} | Emotion: {state.primary_emotion} | Objects: {objs} | Activity: {state.activity}")

    def on_vlm_result(result):
        print(f"[VLM] {result.trigger}: {result.description}")

    pipeline = HybridVisionPipeline(
        enable_vlm=not args.no_vlm,
        enable_emotion=not args.no_emotion,
        enable_yolo=not args.no_yolo,
        vlm_interval=args.vlm_interval,
        vlm_model=args.vlm_model,
        yolo_model=args.yolo_model,
        yolo_interval=args.yolo_interval,
        on_state_change=on_state_change,
        on_vlm_result=on_vlm_result,
    )

    print("="*60)
    print("Hybrid Vision Pipeline")
    print(f"  VLM: {'enabled' if not args.no_vlm else 'disabled'} (every {args.vlm_interval}s)")
    print(f"  Emotion: {'enabled' if not args.no_emotion else 'disabled'}")
    print(f"  YOLO: {'enabled' if not args.no_yolo else 'disabled'} ({args.yolo_model}, every {args.yolo_interval} frames)")
    print("  Press 'q' to quit, 'v' to manually trigger VLM")
    print("="*60)

    pipeline.run_loop(show_ui=not args.no_ui)
