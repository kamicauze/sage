#!/usr/bin/env python3
"""
Vision Service for Sage
Runs the hybrid vision pipeline and publishes state to MQTT.

MQTT Topics Published:
  sage/vision/state       - Current vision state (JSON)
  sage/vision/face        - Face detection events
  sage/vision/vlm         - VLM analysis results
  sage/vision/presence    - Simple presence (true/false)

MQTT Topics Subscribed:
  sage/vision/request     - Request VLM analysis on-demand
  sage/vision/config      - Update configuration
"""

import os
import sys
import json
import time
import signal
import argparse

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import paho.mqtt.client as mqtt
from .hybrid_pipeline import HybridVisionPipeline, VisionState, VLMResult, FastResult


class VisionService:
    """MQTT-enabled vision service for Sage"""

    def __init__(
        self,
        mqtt_host: str = "localhost",
        mqtt_port: int = 1883,
        location: str = "office",  # office, living, car
        camera_index: int = 0,
        vlm_enabled: bool = True,
        vlm_interval: float = 60.0,
        vlm_model: str = "moondream",
        ollama_host: str = "http://localhost:11434",
        yolo_enabled: bool = True,
        yolo_model: str = "yolov8n",
        yolo_interval: int = 5,
    ):
        self.location = location
        self.mqtt_host = mqtt_host
        self.mqtt_port = mqtt_port

        # MQTT client
        self.mqtt = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.mqtt.on_connect = self._on_mqtt_connect
        self.mqtt.on_message = self._on_mqtt_message

        # Vision pipeline
        self.pipeline = HybridVisionPipeline(
            camera_index=camera_index,
            enable_vlm=vlm_enabled,
            vlm_interval=vlm_interval,
            vlm_model=vlm_model,
            ollama_host=ollama_host,
            enable_yolo=yolo_enabled,
            yolo_model=yolo_model,
            yolo_interval=yolo_interval,
            on_state_change=self._on_state_change,
            on_vlm_result=self._on_vlm_result,
        )

        # State tracking for debouncing
        self.last_presence = None
        self.last_publish_time = 0
        self.publish_interval = 0.5  # Don't spam MQTT

        # Running flag
        self.running = False

    def _on_mqtt_connect(self, client, userdata, flags, reason_code, properties=None):
        print(f"[MQTT] Connected to {self.mqtt_host}:{self.mqtt_port}")
        # Subscribe to control topics
        client.subscribe(f"sage/vision/{self.location}/request")
        client.subscribe(f"sage/vision/{self.location}/config")
        client.subscribe("sage/vision/request")  # Global request

    def _on_mqtt_message(self, client, userdata, msg):
        topic = msg.topic
        try:
            payload = json.loads(msg.payload.decode()) if msg.payload else {}
        except:
            payload = msg.payload.decode()

        if "request" in topic:
            # Request VLM analysis
            print(f"[MQTT] VLM request received")
            self.pipeline.request_vlm()

        elif "config" in topic:
            # Update config
            if isinstance(payload, dict):
                if "vlm_interval" in payload:
                    self.pipeline.vlm_interval = float(payload["vlm_interval"])
                if "enable_vlm" in payload:
                    self.pipeline.enable_vlm = bool(payload["enable_vlm"])
                if "enable_emotion" in payload:
                    self.pipeline.enable_emotion = bool(payload["enable_emotion"])
                if "enable_yolo" in payload:
                    self.pipeline.enable_yolo = bool(payload["enable_yolo"])
                if "yolo_interval" in payload:
                    self.pipeline.yolo_interval = int(payload["yolo_interval"])
                print(f"[MQTT] Config updated: {payload}")

    def _on_state_change(self, state: VisionState):
        """Called when vision state changes"""
        now = time.time()

        # Debounce rapid updates
        if now - self.last_publish_time < self.publish_interval:
            return

        # Publish full state
        state_dict = state.to_dict()
        state_dict["location"] = self.location
        state_dict["timestamp"] = now

        self.mqtt.publish(
            f"sage/vision/{self.location}/state",
            json.dumps(state_dict),
            qos=0
        )

        # Publish presence change (debounced)
        presence = state.face_detected
        if presence != self.last_presence:
            payload = json.dumps({
                "present": presence,
                "presence": presence,
                "motion": presence,
                "people_count": state.people_count,
                "timestamp": now,
                "source": "vision"
            })
            # Legacy topic used by some older services.
            self.mqtt.publish(
                f"sage/presence/{self.location}",
                payload,
                qos=1
            )
            # Canonical topic consumed by the Brain parser.
            self.mqtt.publish(
                f"sage/sensors/{self.location}/presence",
                payload,
                qos=1
            )
            self.last_presence = presence
            print(f"[Vision] Presence: {'detected' if presence else 'absent'}")

        self.last_publish_time = now

    def _on_vlm_result(self, result: VLMResult):
        """Called when VLM produces a result"""
        self.mqtt.publish(
            f"sage/vision/{self.location}/vlm",
            json.dumps({
                "location": self.location,
                "trigger": result.trigger,
                "description": result.description,
                "activity": result.activity,
                "mood": result.mood,
                "latency_ms": result.latency_ms,
                "timestamp": result.timestamp
            }),
            qos=1
        )

    def start(self):
        """Start the vision service"""
        self.running = True

        # Connect MQTT
        try:
            self.mqtt.connect(self.mqtt_host, self.mqtt_port, 60)
            self.mqtt.loop_start()
        except Exception as e:
            print(f"[MQTT] Connection failed: {e}")
            print("[MQTT] Continuing without MQTT...")

        # Publish online status
        self.mqtt.publish(
            f"sage/vision/{self.location}/status",
            json.dumps({"status": "online", "timestamp": time.time()}),
            qos=1,
            retain=True
        )

        # Start vision pipeline
        self.pipeline.start()

    def stop(self):
        """Stop the vision service"""
        self.running = False

        # Publish offline status
        self.mqtt.publish(
            f"sage/vision/{self.location}/status",
            json.dumps({"status": "offline", "timestamp": time.time()}),
            qos=1,
            retain=True
        )

        self.pipeline.stop()
        self.mqtt.loop_stop()
        self.mqtt.disconnect()

    def run(self, show_ui: bool = False):
        """Run the service"""
        self.start()

        # Handle signals
        def signal_handler(sig, frame):
            print("\n[Vision] Shutting down...")
            self.running = False

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Main loop
        self.pipeline.run_loop(show_ui=show_ui)
        self.stop()


def main():
    parser = argparse.ArgumentParser(description="Sage Vision Service")
    parser.add_argument('--location', type=str, default='office',
                        choices=['office', 'living', 'car'],
                        help='Location name for MQTT topics')
    parser.add_argument('--camera', type=int, default=0,
                        help='Camera index')
    parser.add_argument('--mqtt-host', type=str, default='localhost',
                        help='MQTT broker host')
    parser.add_argument('--mqtt-port', type=int, default=1883,
                        help='MQTT broker port')
    parser.add_argument('--ollama-host', type=str, default='http://localhost:11434',
                        help='Ollama API host')
    parser.add_argument('--vlm-model', type=str, default='moondream',
                        help='VLM model name')
    parser.add_argument('--vlm-interval', type=float, default=60,
                        help='VLM trigger interval in seconds')
    parser.add_argument('--no-vlm', action='store_true',
                        help='Disable VLM')
    parser.add_argument('--no-yolo', action='store_true',
                        help='Disable YOLO object detection')
    parser.add_argument('--yolo-model', type=str, default='yolov8n',
                        help='YOLO model (yolov8n, yolov8s, yolov8m)')
    parser.add_argument('--yolo-interval', type=int, default=5,
                        help='Run YOLO every N frames')
    parser.add_argument('--ui', action='store_true',
                        help='Show UI window')

    args = parser.parse_args()

    print("="*60)
    print(f"Sage Vision Service - {args.location.upper()}")
    print("="*60)
    print(f"  Camera: {args.camera}")
    print(f"  MQTT: {args.mqtt_host}:{args.mqtt_port}")
    print(f"  VLM: {'disabled' if args.no_vlm else f'{args.vlm_model} (every {args.vlm_interval}s)'}")
    print(f"  YOLO: {'disabled' if args.no_yolo else f'{args.yolo_model} (every {args.yolo_interval} frames)'}")
    print(f"  Topics: sage/vision/{args.location}/*")
    print("="*60)

    service = VisionService(
        mqtt_host=args.mqtt_host,
        mqtt_port=args.mqtt_port,
        location=args.location,
        camera_index=args.camera,
        vlm_enabled=not args.no_vlm,
        vlm_interval=args.vlm_interval,
        vlm_model=args.vlm_model,
        ollama_host=args.ollama_host,
        yolo_enabled=not args.no_yolo,
        yolo_model=args.yolo_model,
        yolo_interval=args.yolo_interval,
    )

    service.run(show_ui=args.ui)


if __name__ == "__main__":
    main()
