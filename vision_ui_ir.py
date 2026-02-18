#!/usr/bin/env python3
"""Vision UI - IR Optimized for Diverse Skin Tones
Uses grayscale + histogram equalization for fairer detection
"""

import cv2
import time
import numpy as np
from insightface.app import FaceAnalysis
from deepface import DeepFace

# Colors (BGR)
GREEN = (0, 255, 0)
CYAN = (255, 255, 0)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
MAGENTA = (255, 0, 255)

EMOTION_COLORS = {
    'happy': (0, 255, 100),
    'sad': (255, 100, 100),
    'angry': (0, 0, 255),
    'fear': (255, 0, 255),
    'surprise': (0, 255, 255),
    'disgust': (0, 150, 0),
    'neutral': (200, 200, 200)
}

def draw_text_with_bg(frame, text, pos, font_scale=0.6, color=WHITE, bg_color=BLACK):
    font = cv2.FONT_HERSHEY_SIMPLEX
    thickness = 1
    (w, h), _ = cv2.getTextSize(text, font, font_scale, thickness)
    x, y = pos
    cv2.rectangle(frame, (x-2, y-h-4), (x+w+2, y+4), bg_color, -1)
    cv2.putText(frame, text, (x, y), font, font_scale, color, thickness)

def preprocess_for_ir(frame):
    """
    Preprocess frame for IR-optimized face detection.
    This helps normalize skin tone differences.
    """
    # Convert to grayscale (IR cameras output near-IR in luminance channel)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
    # This normalizes lighting and reduces skin tone bias
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    equalized = clahe.apply(gray)

    # Convert back to BGR for models that expect 3 channels
    equalized_bgr = cv2.cvtColor(equalized, cv2.COLOR_GRAY2BGR)

    return equalized_bgr, equalized

def main():
    print("="*60)
    print("Vision UI - IR Optimized Mode")
    print("Uses histogram equalization for skin tone fairness")
    print("="*60)

    # Initialize InsightFace (works well with preprocessed images)
    print("\nLoading InsightFace...")
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

    # Try to disable auto white balance for more consistent IR
    cap.set(cv2.CAP_PROP_AUTO_WB, 0)

    if not cap.isOpened():
        print("ERROR: Cannot open camera")
        return

    print("\nControls:")
    print("  'q' - Quit")
    print("  'm' - Toggle mode (Color / IR-Equalized / Side-by-side)")
    print("  'e' - Toggle emotion detection")
    print()

    frame_count = 0
    fps_start = time.time()
    fps = 0

    # Display modes: 0=color, 1=IR-equalized, 2=side-by-side
    display_mode = 2
    mode_names = ['Color', 'IR-Equalized', 'Side-by-Side']
    enable_emotion = True
    emotion_interval = 8
    last_emotion = "..."

    cv2.namedWindow('Sage Vision IR', cv2.WINDOW_NORMAL)
    cv2.resizeWindow('Sage Vision IR', 1280, 480)

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            start = time.time()

            # Preprocess for IR/equalized detection
            processed_bgr, processed_gray = preprocess_for_ir(frame)

            # Run face detection on processed image (fairer across skin tones)
            faces = face_app.get(processed_bgr)
            detect_time = (time.time() - start) * 1000

            # Prepare display frames
            if display_mode == 0:
                display = frame.copy()
            elif display_mode == 1:
                display = processed_bgr.copy()
            else:  # Side-by-side
                display = np.hstack([frame, processed_bgr])

            # Calculate offset for side-by-side mode
            x_offset = frame.shape[1] if display_mode == 2 else 0

            for i, face in enumerate(faces):
                bbox = face.bbox.astype(int)
                x1, y1, x2, y2 = bbox
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(frame.shape[1], x2), min(frame.shape[0], y2)

                age = int(getattr(face, 'age', 0))
                gender = 'M' if getattr(face, 'gender', None) == 1 else 'F'
                conf = face.det_score if hasattr(face, 'det_score') else 0

                # Emotion detection on original color frame (periodically)
                if enable_emotion and frame_count % emotion_interval == 0:
                    try:
                        face_crop = frame[y1:y2, x1:x2]
                        if face_crop.size > 0 and min(face_crop.shape[:2]) > 30:
                            result = DeepFace.analyze(
                                face_crop,
                                actions=['emotion'],
                                detector_backend='skip',  # Already detected
                                enforce_detection=False,
                                silent=True
                            )
                            if result:
                                last_emotion = result[0]['dominant_emotion']
                    except:
                        pass

                box_color = EMOTION_COLORS.get(last_emotion, GREEN)

                # Draw on color side (or single frame)
                if display_mode != 1:
                    cv2.rectangle(display, (x1, y1), (x2, y2), box_color, 2)
                    draw_text_with_bg(display, f"{gender} ~{age}y", (x1, y1-10))
                    draw_text_with_bg(display, f"{last_emotion}", (x1, y2+20), color=box_color)
                    draw_text_with_bg(display, f"{conf:.0%}", (x2-45, y1-10), color=GREEN)

                # Draw on processed side (side-by-side mode)
                if display_mode == 2:
                    cv2.rectangle(display, (x1+x_offset, y1), (x2+x_offset, y2), CYAN, 2)
                    draw_text_with_bg(display, f"{gender} ~{age}y", (x1+x_offset, y1-10))
                    draw_text_with_bg(display, f"conf: {conf:.0%}", (x1+x_offset, y2+20), color=CYAN)
                elif display_mode == 1:
                    cv2.rectangle(display, (x1, y1), (x2, y2), CYAN, 2)
                    draw_text_with_bg(display, f"{gender} ~{age}y | {last_emotion}", (x1, y1-10))
                    draw_text_with_bg(display, f"conf: {conf:.0%}", (x1, y2+20), color=CYAN)

            # Draw stats
            stats = f"FPS: {fps:.1f} | Detect: {detect_time:.0f}ms | Mode: {mode_names[display_mode]}"
            draw_text_with_bg(display, stats, (10, 25), font_scale=0.5)

            if display_mode == 2:
                draw_text_with_bg(display, "Original", (10, 50), font_scale=0.4, color=GREEN)
                draw_text_with_bg(display, "IR-Equalized (detection runs here)",
                                  (x_offset+10, 50), font_scale=0.4, color=CYAN)

            hint = "'q' quit | 'm' mode | 'e' emotion"
            draw_text_with_bg(display, hint, (10, display.shape[0]-15), font_scale=0.4)

            # FPS calculation
            frame_count += 1
            if frame_count % 30 == 0:
                fps = 30 / (time.time() - fps_start)
                fps_start = time.time()

            cv2.imshow('Sage Vision IR', display)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('m'):
                display_mode = (display_mode + 1) % 3
            elif key == ord('e'):
                enable_emotion = not enable_emotion
                print(f"Emotion detection: {'ON' if enable_emotion else 'OFF'}")

    except KeyboardInterrupt:
        print("\nStopped")
    finally:
        cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
