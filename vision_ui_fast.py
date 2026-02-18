#!/usr/bin/env python3
"""Fast Vision UI - InsightFace only (no TensorFlow delay)"""

import cv2
import time
import numpy as np
from insightface.app import FaceAnalysis

# Colors (BGR)
GREEN = (0, 255, 0)
CYAN = (255, 255, 0)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

def draw_text_with_bg(frame, text, pos, font_scale=0.6, color=WHITE, bg_color=BLACK):
    font = cv2.FONT_HERSHEY_SIMPLEX
    (w, h), _ = cv2.getTextSize(text, font, font_scale, 1)
    x, y = pos
    cv2.rectangle(frame, (x-2, y-h-4), (x+w+2, y+4), bg_color, -1)
    cv2.putText(frame, text, (x, y), font, font_scale, color, 1)

def preprocess_clahe(frame):
    """CLAHE preprocessing for fairer skin tone detection"""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    equalized = clahe.apply(gray)
    return cv2.cvtColor(equalized, cv2.COLOR_GRAY2BGR), equalized

def main():
    print("Loading InsightFace...")
    face_app = FaceAnalysis(
        allowed_modules=['detection', 'genderage'],
        providers=['CUDAExecutionProvider', 'CPUExecutionProvider']
    )
    face_app.prepare(ctx_id=0, det_size=(640, 480))

    cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
    if not cap.isOpened():
        cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    if not cap.isOpened():
        print("ERROR: Cannot open camera")
        return

    print("\nVision UI Ready - Press 'q' to quit, 'm' to toggle mode")

    frame_count = 0
    fps_start = time.time()
    fps = 0
    show_processed = True  # Show side-by-side

    cv2.namedWindow('Sage Vision', cv2.WINDOW_NORMAL)
    cv2.resizeWindow('Sage Vision', 1280, 480)

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        start = time.time()
        processed_bgr, processed_gray = preprocess_clahe(frame)

        # Detect on processed (equalized) image
        faces = face_app.get(processed_bgr)
        detect_time = (time.time() - start) * 1000

        # Display
        if show_processed:
            display = np.hstack([frame, processed_bgr])
            offset = frame.shape[1]
        else:
            display = frame.copy()
            offset = 0

        for face in faces:
            bbox = face.bbox.astype(int)
            x1, y1, x2, y2 = bbox
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(frame.shape[1], x2), min(frame.shape[0], y2)

            age = int(getattr(face, 'age', 0))
            gender = 'Male' if getattr(face, 'gender', None) == 1 else 'Female'
            conf = face.det_score if hasattr(face, 'det_score') else 0

            # Draw on original
            cv2.rectangle(display, (x1, y1), (x2, y2), GREEN, 2)
            draw_text_with_bg(display, f"{gender}, ~{age}y", (x1, y1-10))
            draw_text_with_bg(display, f"{conf:.0%}", (x2-50, y1-10), color=GREEN)

            # Draw on processed side
            if show_processed:
                cv2.rectangle(display, (x1+offset, y1), (x2+offset, y2), CYAN, 2)
                draw_text_with_bg(display, f"{gender}, ~{age}y", (x1+offset, y1-10))

        # Stats
        draw_text_with_bg(display, f"FPS: {fps:.1f} | {detect_time:.0f}ms | Faces: {len(faces)}", (10, 25), 0.5)
        if show_processed:
            draw_text_with_bg(display, "Original", (10, 50), 0.4, GREEN)
            draw_text_with_bg(display, "IR-Equalized", (offset+10, 50), 0.4, CYAN)
        draw_text_with_bg(display, "'q' quit | 'm' mode", (10, display.shape[0]-15), 0.4)

        frame_count += 1
        if frame_count % 30 == 0:
            fps = 30 / (time.time() - fps_start)
            fps_start = time.time()

        cv2.imshow('Sage Vision', display)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('m'):
            show_processed = not show_processed
            if show_processed:
                cv2.resizeWindow('Sage Vision', 1280, 480)
            else:
                cv2.resizeWindow('Sage Vision', 640, 480)

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
