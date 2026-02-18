#!/usr/bin/env python3
"""Full face detection + emotion recognition test for Sage
Uses InsightFace for fast face detection and DeepFace for emotion analysis
"""

import cv2
import time
import numpy as np
from insightface.app import FaceAnalysis
from deepface import DeepFace

def main():
    # Initialize InsightFace for fast detection
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

    print("\n" + "="*70)
    print("Face + Emotion Detection (InsightFace + DeepFace)")
    print("Press Ctrl+C to stop")
    print("="*70 + "\n")

    frame_count = 0
    emotion_interval = 5  # Run emotion detection every N frames (it's slower)
    last_emotion = "unknown"

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Camera read failed")
                break

            start = time.time()
            faces = face_app.get(frame)
            detect_time = (time.time() - start) * 1000

            if faces:
                for i, face in enumerate(faces):
                    bbox = face.bbox.astype(int)
                    x1, y1, x2, y2 = bbox

                    # Ensure valid crop
                    x1, y1 = max(0, x1), max(0, y1)
                    x2, y2 = min(frame.shape[1], x2), min(frame.shape[0], y2)

                    age = int(getattr(face, 'age', 0))
                    gender = 'M' if getattr(face, 'gender', None) == 1 else 'F'
                    conf = face.det_score if hasattr(face, 'det_score') else 0

                    # Run emotion detection periodically (slower)
                    emotion_time = 0
                    if frame_count % emotion_interval == 0:
                        try:
                            face_crop = frame[y1:y2, x1:x2]
                            if face_crop.size > 0 and face_crop.shape[0] > 20 and face_crop.shape[1] > 20:
                                emo_start = time.time()
                                result = DeepFace.analyze(
                                    face_crop,
                                    actions=['emotion'],
                                    enforce_detection=False,
                                    silent=True
                                )
                                emotion_time = (time.time() - emo_start) * 1000
                                if result and len(result) > 0:
                                    last_emotion = result[0]['dominant_emotion']
                        except Exception as e:
                            pass  # Silently skip emotion detection errors

                    total_time = detect_time + emotion_time

                    print(f"[Face {i+1}] pos=({x1},{y1})-({x2},{y2}) | "
                          f"conf={conf:.2f} | age={age:2d} | gender={gender} | "
                          f"emotion={last_emotion:10s} | "
                          f"detect={detect_time:.0f}ms emo={emotion_time:.0f}ms total={total_time:.0f}ms")
            else:
                if frame_count % 20 == 0:
                    print(f"No face | {detect_time:.0f}ms")

            frame_count += 1
            time.sleep(0.05)

    except KeyboardInterrupt:
        print("\nStopped")
    finally:
        cap.release()

if __name__ == "__main__":
    main()
