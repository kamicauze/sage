#!/usr/bin/env python3
"""Simple face detection test using InsightFace only"""

import cv2
import time
from insightface.app import FaceAnalysis

def main():
    # Initialize face detector with all modules
    print("Loading InsightFace (detection + age/gender)...")
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

    print("\n" + "="*60)
    print("Face Detection Running (InsightFace)")
    print("Press Ctrl+C to stop")
    print("="*60 + "\n")

    frame_count = 0
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Camera read failed")
                break

            start = time.time()
            faces = face_app.get(frame)
            latency = (time.time() - start) * 1000

            if faces:
                for i, face in enumerate(faces):
                    bbox = face.bbox.astype(int)
                    x1, y1, x2, y2 = bbox

                    # Get age/gender if available
                    age = getattr(face, 'age', None)
                    gender = getattr(face, 'gender', None)
                    gender_str = 'M' if gender == 1 else 'F' if gender == 0 else '?'

                    det_score = face.det_score if hasattr(face, 'det_score') else 0

                    print(f"[Face {i+1}] pos=({x1},{y1})-({x2},{y2}) | "
                          f"conf={det_score:.2f} | age={age} | gender={gender_str} | "
                          f"{latency:.0f}ms")
            else:
                if frame_count % 20 == 0:
                    print(f"No face | {latency:.0f}ms")

            frame_count += 1
            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\nStopped")
    finally:
        cap.release()

if __name__ == "__main__":
    main()
