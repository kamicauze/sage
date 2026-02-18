#!/usr/bin/env python3
"""Vision UI - Face detection with live camera view"""

import cv2
import time
import numpy as np
from insightface.app import FaceAnalysis
from deepface import DeepFace

# Colors (BGR)
GREEN = (0, 255, 0)
BLUE = (255, 180, 0)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

def draw_text_with_bg(frame, text, pos, font_scale=0.6, color=WHITE, bg_color=BLACK):
    """Draw text with background for better visibility"""
    font = cv2.FONT_HERSHEY_SIMPLEX
    thickness = 1
    (w, h), _ = cv2.getTextSize(text, font, font_scale, thickness)
    x, y = pos
    cv2.rectangle(frame, (x-2, y-h-4), (x+w+2, y+4), bg_color, -1)
    cv2.putText(frame, text, (x, y), font, font_scale, color, thickness)

def main():
    print("Loading InsightFace...")
    face_app = FaceAnalysis(
        allowed_modules=['detection', 'genderage'],
        providers=['CUDAExecutionProvider', 'CPUExecutionProvider']
    )
    face_app.prepare(ctx_id=0, det_size=(640, 480))

    # Open camera
    cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
    if not cap.isOpened():
        cap = cv2.VideoCapture(0)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    if not cap.isOpened():
        print("ERROR: Cannot open camera")
        return

    print("\n" + "="*50)
    print("Vision UI - Press 'q' to quit")
    print("="*50 + "\n")

    frame_count = 0
    emotion_interval = 10  # Check emotion every N frames
    last_emotions = {}  # face_id -> emotion
    fps_start = time.time()
    fps = 0

    cv2.namedWindow('Sage Vision', cv2.WINDOW_NORMAL)
    cv2.resizeWindow('Sage Vision', 960, 720)

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            start = time.time()
            faces = face_app.get(frame)
            detect_time = (time.time() - start) * 1000

            for i, face in enumerate(faces):
                bbox = face.bbox.astype(int)
                x1, y1, x2, y2 = bbox
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(frame.shape[1], x2), min(frame.shape[0], y2)

                age = int(getattr(face, 'age', 0))
                gender = 'Male' if getattr(face, 'gender', None) == 1 else 'Female'
                conf = face.det_score if hasattr(face, 'det_score') else 0

                # Get emotion periodically
                emotion = last_emotions.get(i, "...")
                if frame_count % emotion_interval == 0:
                    try:
                        face_crop = frame[y1:y2, x1:x2]
                        if face_crop.size > 0 and min(face_crop.shape[:2]) > 30:
                            result = DeepFace.analyze(
                                face_crop,
                                actions=['emotion'],
                                enforce_detection=False,
                                silent=True
                            )
                            if result:
                                emotion = result[0]['dominant_emotion']
                                last_emotions[i] = emotion
                    except:
                        pass

                # Draw face box
                cv2.rectangle(frame, (x1, y1), (x2, y2), GREEN, 2)

                # Draw corner accents
                corner_len = 15
                cv2.line(frame, (x1, y1), (x1+corner_len, y1), BLUE, 3)
                cv2.line(frame, (x1, y1), (x1, y1+corner_len), BLUE, 3)
                cv2.line(frame, (x2, y1), (x2-corner_len, y1), BLUE, 3)
                cv2.line(frame, (x2, y1), (x2, y1+corner_len), BLUE, 3)
                cv2.line(frame, (x1, y2), (x1+corner_len, y2), BLUE, 3)
                cv2.line(frame, (x1, y2), (x1, y2-corner_len), BLUE, 3)
                cv2.line(frame, (x2, y2), (x2-corner_len, y2), BLUE, 3)
                cv2.line(frame, (x2, y2), (x2, y2-corner_len), BLUE, 3)

                # Draw labels
                draw_text_with_bg(frame, f"{gender}, ~{age}y", (x1, y1-10))
                draw_text_with_bg(frame, f"Emotion: {emotion}", (x1, y2+20))
                draw_text_with_bg(frame, f"{conf:.0%}", (x2-45, y1-10), color=GREEN)

            # Draw stats overlay
            fps_text = f"FPS: {fps:.1f} | Detect: {detect_time:.0f}ms | Faces: {len(faces)}"
            draw_text_with_bg(frame, fps_text, (10, 25), font_scale=0.5)
            draw_text_with_bg(frame, "Press 'q' to quit", (10, frame.shape[0]-15), font_scale=0.4)

            # Calculate FPS
            frame_count += 1
            if frame_count % 30 == 0:
                fps = 30 / (time.time() - fps_start)
                fps_start = time.time()

            cv2.imshow('Sage Vision', frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    except KeyboardInterrupt:
        print("\nStopped")
    finally:
        cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
