#!/usr/bin/env python3
"""Vision UI v2 - Optimized for diverse skin tones
Uses RetinaFace (better performance on darker skin) + multiple backends
"""

import cv2
import time
import numpy as np
from deepface import DeepFace

# Colors (BGR)
GREEN = (0, 255, 0)
BLUE = (255, 180, 0)
CYAN = (255, 255, 0)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

# Emotion color mapping
EMOTION_COLORS = {
    'happy': (0, 255, 100),
    'sad': (255, 100, 100),
    'angry': (0, 0, 255),
    'fear': (255, 0, 255),
    'surprise': (0, 255, 255),
    'disgust': (0, 150, 0),
    'neutral': (200, 200, 200)
}

def draw_text_with_bg(frame, text, pos, font_scale=0.6, color=WHITE, bg_color=BLACK, thickness=1):
    """Draw text with background for better visibility"""
    font = cv2.FONT_HERSHEY_SIMPLEX
    (w, h), _ = cv2.getTextSize(text, font, font_scale, thickness)
    x, y = pos
    cv2.rectangle(frame, (x-2, y-h-4), (x+w+2, y+4), bg_color, -1)
    cv2.putText(frame, text, (x, y), font, font_scale, color, thickness)

def draw_confidence_bar(frame, x, y, w, confidence, label=""):
    """Draw a confidence bar"""
    bar_h = 8
    filled_w = int(w * confidence)
    cv2.rectangle(frame, (x, y), (x+w, y+bar_h), (50, 50, 50), -1)
    color = (0, 255, 0) if confidence > 0.8 else (0, 255, 255) if confidence > 0.5 else (0, 0, 255)
    cv2.rectangle(frame, (x, y), (x+filled_w, y+bar_h), color, -1)
    if label:
        draw_text_with_bg(frame, f"{label}: {confidence:.0%}", (x, y-5), font_scale=0.4)

def main():
    print("="*60)
    print("Vision UI v2 - Optimized for Diverse Skin Tones")
    print("Using RetinaFace detector (better accuracy on darker skin)")
    print("="*60)

    # Open camera
    cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
    if not cap.isOpened():
        cap = cv2.VideoCapture(0)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    if not cap.isOpened():
        print("ERROR: Cannot open camera")
        return

    print("\nInitializing models (first run downloads ~100MB)...")
    print("Press 'q' to quit, 'b' to toggle backend info\n")

    frame_count = 0
    fps_start = time.time()
    fps = 0
    show_backend_info = True

    # Cache for smoother display
    last_results = []
    analysis_interval = 3  # Analyze every N frames

    cv2.namedWindow('Sage Vision v2', cv2.WINDOW_NORMAL)
    cv2.resizeWindow('Sage Vision v2', 960, 720)

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            display_frame = frame.copy()
            start = time.time()

            # Run analysis periodically
            if frame_count % analysis_interval == 0:
                try:
                    results = DeepFace.analyze(
                        frame,
                        actions=['age', 'gender', 'emotion', 'race'],
                        detector_backend='retinaface',  # Better for diverse skin
                        enforce_detection=False,
                        silent=True
                    )
                    last_results = results if isinstance(results, list) else [results]
                except Exception as e:
                    pass  # Keep last results on error

            detect_time = (time.time() - start) * 1000

            # Draw results
            for i, face in enumerate(last_results):
                if 'region' not in face:
                    continue

                region = face['region']
                x, y, w, h = region['x'], region['y'], region['w'], region['h']
                x1, y1, x2, y2 = x, y, x + w, y + h

                # Get attributes
                age = face.get('age', 0)
                gender = face.get('dominant_gender', 'Unknown')
                gender_conf = face.get('gender', {}).get(gender, 0) / 100
                emotion = face.get('dominant_emotion', 'neutral')
                emotion_conf = face.get('emotion', {}).get(emotion, 0) / 100
                race = face.get('dominant_race', 'unknown')
                race_conf = face.get('race', {}).get(race, 0) / 100
                face_conf = face.get('face_confidence', 0.9)

                # Get emotion color
                box_color = EMOTION_COLORS.get(emotion, GREEN)

                # Draw face box with emotion-colored border
                cv2.rectangle(display_frame, (x1, y1), (x2, y2), box_color, 2)

                # Draw corner accents
                corner_len = 20
                cv2.line(display_frame, (x1, y1), (x1+corner_len, y1), CYAN, 3)
                cv2.line(display_frame, (x1, y1), (x1, y1+corner_len), CYAN, 3)
                cv2.line(display_frame, (x2, y1), (x2-corner_len, y1), CYAN, 3)
                cv2.line(display_frame, (x2, y1), (x2, y1+corner_len), CYAN, 3)
                cv2.line(display_frame, (x1, y2), (x1+corner_len, y2), CYAN, 3)
                cv2.line(display_frame, (x1, y2), (x1, y2-corner_len), CYAN, 3)
                cv2.line(display_frame, (x2, y2), (x2-corner_len, y2), CYAN, 3)
                cv2.line(display_frame, (x2, y2), (x2, y2-corner_len), CYAN, 3)

                # Draw info panel to the right of face
                panel_x = x2 + 10
                if panel_x + 150 > frame.shape[1]:
                    panel_x = x1 - 160

                # Labels
                draw_text_with_bg(display_frame, f"{gender}, ~{int(age)}y", (x1, y1-10), color=WHITE)

                # Emotion with confidence bar
                draw_text_with_bg(display_frame, f"{emotion.upper()}", (x1, y2+20),
                                  font_scale=0.7, color=box_color)
                draw_confidence_bar(display_frame, x1, y2+35, w, emotion_conf)

                # Show race detection (for debugging bias)
                if show_backend_info:
                    draw_text_with_bg(display_frame, f"Detected: {race} ({race_conf:.0%})",
                                      (x1, y2+55), font_scale=0.4, color=(150, 150, 150))

            # Draw stats overlay
            stats = f"FPS: {fps:.1f} | Analyze: {detect_time:.0f}ms | Faces: {len(last_results)}"
            draw_text_with_bg(display_frame, stats, (10, 25), font_scale=0.5)
            draw_text_with_bg(display_frame, "Backend: RetinaFace (optimized for diverse skin)",
                              (10, 50), font_scale=0.4, color=CYAN)
            draw_text_with_bg(display_frame, "'q' quit | 'b' toggle info",
                              (10, display_frame.shape[0]-15), font_scale=0.4)

            # Calculate FPS
            frame_count += 1
            if frame_count % 30 == 0:
                fps = 30 / (time.time() - fps_start)
                fps_start = time.time()

            cv2.imshow('Sage Vision v2', display_frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('b'):
                show_backend_info = not show_backend_info

    except KeyboardInterrupt:
        print("\nStopped")
    finally:
        cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
