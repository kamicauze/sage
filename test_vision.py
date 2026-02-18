#!/usr/bin/env python3
"""Face detection + expression recognition test for Sage"""

import cv2
import time
import torch
from insightface.app import FaceAnalysis

# Patch torch.load for HSEmotion (uses old-style checkpoints)
_original_torch_load = torch.load
def _patched_torch_load(*args, **kwargs):
    kwargs.setdefault('weights_only', False)
    return _original_torch_load(*args, **kwargs)
torch.load = _patched_torch_load

from hsemotion.facial_emotions import HSEmotionRecognizer

def main():
    # Initialize face detector
    print("Loading face detector (InsightFace)...")
    face_app = FaceAnalysis(allowed_modules=['detection'], providers=['CUDAExecutionProvider'])
    face_app.prepare(ctx_id=0, det_size=(640, 480))

    # Initialize emotion recognizer
    print("Loading emotion model (HSEmotion)...")
    emotion_model = HSEmotionRecognizer(model_name='enet_b0_8_best_afew')

    # Open camera - try multiple backends
    cap = None
    for backend in [cv2.CAP_V4L2, cv2.CAP_ANY]:
        cap = cv2.VideoCapture(0, backend)
        if cap.isOpened():
            ret, _ = cap.read()
            if ret:
                print(f"Camera opened with backend: {backend}")
                break
            cap.release()

    if cap is None or not cap.isOpened():
        # Fallback: try without backend specification
        cap = cv2.VideoCapture(0)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    if not cap.isOpened():
        print("ERROR: Cannot open camera")
        return

    print("\n" + "="*60)
    print("Face + Expression Detection Running")
    print("Press Ctrl+C to stop")
    print("="*60 + "\n")

    frame_count = 0
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Camera error")
                break

            start = time.time()
            faces = face_app.get(frame)

            if faces:
                for i, face in enumerate(faces):
                    bbox = face.bbox.astype(int)
                    x1, y1, x2, y2 = bbox

                    # Ensure valid crop
                    x1, y1 = max(0, x1), max(0, y1)
                    x2, y2 = min(frame.shape[1], x2), min(frame.shape[0], y2)

                    face_crop = frame[y1:y2, x1:x2]
                    if face_crop.size > 0:
                        emotion, scores = emotion_model.predict_emotions(face_crop, logits=True)
                        latency = (time.time() - start) * 1000

                        print(f"[Face {i+1}] bbox=({x1},{y1})-({x2},{y2}) | "
                              f"Expression: {emotion:10} | Latency: {latency:.0f}ms")
            else:
                latency = (time.time() - start) * 1000
                if frame_count % 10 == 0:  # Print every 10th frame when no face
                    print(f"No face detected | Latency: {latency:.0f}ms")

            frame_count += 1
            time.sleep(0.1)  # ~10 FPS

    except KeyboardInterrupt:
        print("\nStopped by user")
    finally:
        cap.release()
        print("Camera released")

if __name__ == "__main__":
    main()
