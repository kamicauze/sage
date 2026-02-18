#!/usr/bin/env python3
"""
Drive Buddy Service
Complete driver assistance system with vision, OBD-II, GPS, and voice.

MQTT Topics Published:
  sage/car/status           - Service status
  sage/car/driver           - Driver state (attention, drowsiness)
  sage/car/obd              - Vehicle data (speed, rpm, fuel, etc.)
  sage/car/gps              - GPS data (position, speed, heading)
  sage/car/alert            - Safety alerts

MQTT Topics Subscribed:
  sage/car/command          - Voice commands
  sage/car/config           - Configuration updates
"""

import os
import sys
import json
import time
import signal
import argparse
import threading
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import paho.mqtt.client as mqtt

from drive_buddy.driver_monitor import DriverMonitor, DriverState
from drive_buddy.obd_reader import OBDReader, SimulatedOBDReader, VehicleState
from drive_buddy.gps_reader import GPSReader, SimulatedGPSReader, GPSState


class DriveBuddyService:
    """
    Complete Drive Buddy service.

    Features:
    - Driver attention monitoring (drowsiness, distraction)
    - Vehicle data from OBD-II (speed, rpm, fuel)
    - GPS location and speed
    - Safety alerts via MQTT (and TTS)
    - Voice commands
    """

    def __init__(
        self,
        mqtt_host: str = "localhost",
        mqtt_port: int = 1883,
        camera_index: int = 0,
        obd_port: str = "auto",
        gps_port: str = "/dev/ttyUSB0",
        simulate: bool = False,
        enable_vision: bool = True,
        enable_obd: bool = True,
        enable_gps: bool = True,
    ):
        self.mqtt_host = mqtt_host
        self.mqtt_port = mqtt_port
        self.simulate = simulate
        self.enable_vision = enable_vision
        self.enable_obd = enable_obd
        self.enable_gps = enable_gps

        # MQTT
        self.mqtt = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.mqtt.on_connect = self._on_mqtt_connect
        self.mqtt.on_message = self._on_mqtt_message

        # Components
        self.driver_monitor = None
        self.obd_reader = None
        self.gps_reader = None

        # State
        self.running = False
        self.last_alert_time = {}

        # Initialize components
        if enable_vision:
            self.driver_monitor = DriverMonitor(
                camera_index=camera_index,
                on_state_change=self._on_driver_state,
                on_alert=self._on_driver_alert,
            )

        if enable_obd:
            OBDClass = SimulatedOBDReader if simulate else OBDReader
            self.obd_reader = OBDClass(
                port=obd_port,
                poll_interval=0.5,
                on_state_change=self._on_obd_state,
            )

        if enable_gps:
            GPSClass = SimulatedGPSReader if simulate else GPSReader
            self.gps_reader = GPSClass(
                port=gps_port,
                on_position_change=self._on_gps_state,
            )

    def _on_mqtt_connect(self, client, userdata, flags, reason_code, properties=None):
        print(f"[MQTT] Connected to {self.mqtt_host}:{self.mqtt_port}")
        client.subscribe("sage/car/command")
        client.subscribe("sage/car/config")

        # Publish online status
        client.publish("sage/car/status", json.dumps({
            "status": "online",
            "components": {
                "vision": self.enable_vision,
                "obd": self.enable_obd,
                "gps": self.enable_gps,
            },
            "timestamp": time.time()
        }), qos=1, retain=True)

    def _on_mqtt_message(self, client, userdata, msg):
        topic = msg.topic
        try:
            payload = json.loads(msg.payload.decode()) if msg.payload else {}
        except:
            payload = msg.payload.decode()

        if topic == "sage/car/command":
            self._handle_command(payload)
        elif topic == "sage/car/config":
            self._handle_config(payload)

    def _handle_command(self, payload):
        """Handle voice commands"""
        cmd = payload.get("command", "") if isinstance(payload, dict) else str(payload)
        print(f"[Command] {cmd}")

        # TODO: Process commands like "navigate to...", "play music", etc.

    def _handle_config(self, payload):
        """Handle config updates"""
        if isinstance(payload, dict):
            # Update thresholds, etc.
            print(f"[Config] Updated: {payload}")

    def _on_driver_state(self, state: DriverState):
        """Publish driver state"""
        self.mqtt.publish("sage/car/driver", json.dumps({
            "face_detected": state.face_detected,
            "eyes_open": state.eyes_open,
            "attention_state": state.attention_state,
            "drowsiness_score": state.drowsiness_score,
            "looking_at_road": state.looking_at_road,
            "gaze_direction": state.gaze_direction,
            "blink_count": state.blink_count,
            "yawn_count": state.yawn_count,
            "timestamp": state.timestamp
        }))

    def _on_driver_alert(self, alert_type: str, message: str):
        """Handle driver safety alert"""
        self.mqtt.publish("sage/car/alert", json.dumps({
            "type": alert_type,
            "message": message,
            "priority": "high" if alert_type in ["eyes_closed", "drowsy"] else "medium",
            "timestamp": time.time()
        }), qos=1)

        # Also publish to voice for TTS
        self.mqtt.publish("sage/voice/response", json.dumps({
            "text": message,
            "priority": "high",
            "source": "drive_buddy"
        }))

    def _on_obd_state(self, state: VehicleState):
        """Publish vehicle state"""
        self.mqtt.publish("sage/car/obd", json.dumps({
            "speed_kmh": state.speed_kmh,
            "rpm": state.rpm,
            "throttle_percent": state.throttle_percent,
            "fuel_level_percent": state.fuel_level_percent,
            "coolant_temp_c": state.coolant_temp_c,
            "engine_load_percent": state.engine_load_percent,
            "mil_on": state.mil_on,
            "timestamp": state.timestamp
        }))

        # Check for vehicle alerts
        self._check_vehicle_alerts(state)

    def _on_gps_state(self, state: GPSState):
        """Publish GPS state"""
        self.mqtt.publish("sage/car/gps", json.dumps({
            "latitude": state.latitude,
            "longitude": state.longitude,
            "altitude_m": state.altitude_m,
            "speed_kmh": state.speed_kmh,
            "heading": state.heading,
            "satellites": state.satellites,
            "has_fix": state.has_fix,
            "timestamp": state.timestamp
        }))

        # Simple presence update
        self.mqtt.publish("sage/presence/car", json.dumps({
            "present": True,
            "timestamp": state.timestamp
        }))

    def _check_vehicle_alerts(self, state: VehicleState):
        """Check for vehicle-related alerts"""
        now = time.time()

        def should_alert(alert_type, cooldown=300):
            last = self.last_alert_time.get(alert_type, 0)
            if now - last > cooldown:
                self.last_alert_time[alert_type] = now
                return True
            return False

        # High coolant temperature
        if state.coolant_temp_c > 105:
            if should_alert("high_temp"):
                self._send_alert("high_temp", "Engine temperature is high. Consider pulling over.", "high")

        # Low fuel
        if state.fuel_level_percent < 15:
            if should_alert("low_fuel", 600):
                self._send_alert("low_fuel", f"Fuel is low at {state.fuel_level_percent:.0f}%", "medium")

        # Check engine light
        if state.mil_on:
            if should_alert("check_engine", 3600):
                self._send_alert("check_engine", "Check engine light is on. Consider getting it checked.", "medium")

    def _send_alert(self, alert_type: str, message: str, priority: str = "medium"):
        """Send an alert"""
        self.mqtt.publish("sage/car/alert", json.dumps({
            "type": alert_type,
            "message": message,
            "priority": priority,
            "timestamp": time.time()
        }), qos=1)

        # Voice alert
        self.mqtt.publish("sage/voice/response", json.dumps({
            "text": message,
            "priority": priority,
            "source": "drive_buddy"
        }))

    def start(self):
        """Start all components"""
        self.running = True

        # Connect MQTT
        try:
            self.mqtt.connect(self.mqtt_host, self.mqtt_port, 60)
            self.mqtt.loop_start()
        except Exception as e:
            print(f"[MQTT] Connection failed: {e}")

        # Start OBD reader
        if self.obd_reader:
            self.obd_reader.start()

        # Start GPS reader
        if self.gps_reader:
            self.gps_reader.start()

        # Driver monitor runs in main thread (below)
        print("[DriveBuddy] Service started")

    def stop(self):
        """Stop all components"""
        self.running = False

        # Publish offline status
        self.mqtt.publish("sage/car/status", json.dumps({
            "status": "offline",
            "timestamp": time.time()
        }), qos=1, retain=True)

        if self.driver_monitor:
            self.driver_monitor.stop()
        if self.obd_reader:
            self.obd_reader.stop()
        if self.gps_reader:
            self.gps_reader.stop()

        self.mqtt.loop_stop()
        self.mqtt.disconnect()
        print("[DriveBuddy] Service stopped")

    def run(self, show_ui: bool = False):
        """Run the service"""
        self.start()

        # Handle signals
        def signal_handler(sig, frame):
            print("\n[DriveBuddy] Shutting down...")
            self.running = False

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Run driver monitor in main thread (with UI if requested)
        if self.driver_monitor:
            self.driver_monitor.run_loop(show_ui=show_ui)
        else:
            # No vision - just wait
            while self.running:
                time.sleep(1)

        self.stop()


def main():
    parser = argparse.ArgumentParser(description="Drive Buddy Service")
    parser.add_argument('--mqtt-host', type=str, default='localhost')
    parser.add_argument('--mqtt-port', type=int, default=1883)
    parser.add_argument('--camera', type=int, default=0)
    parser.add_argument('--obd-port', type=str, default='auto')
    parser.add_argument('--gps-port', type=str, default='/dev/ttyUSB0')
    parser.add_argument('--simulate', action='store_true', help='Use simulated OBD/GPS')
    parser.add_argument('--no-vision', action='store_true')
    parser.add_argument('--no-obd', action='store_true')
    parser.add_argument('--no-gps', action='store_true')
    parser.add_argument('--ui', action='store_true', help='Show driver monitor UI')

    args = parser.parse_args()

    print("="*60)
    print("Drive Buddy - Your Driving Companion")
    print("="*60)
    print(f"  MQTT: {args.mqtt_host}:{args.mqtt_port}")
    print(f"  Vision: {'disabled' if args.no_vision else 'enabled'}")
    print(f"  OBD-II: {'disabled' if args.no_obd else ('simulated' if args.simulate else args.obd_port)}")
    print(f"  GPS: {'disabled' if args.no_gps else ('simulated' if args.simulate else args.gps_port)}")
    print("="*60)

    service = DriveBuddyService(
        mqtt_host=args.mqtt_host,
        mqtt_port=args.mqtt_port,
        camera_index=args.camera,
        obd_port=args.obd_port,
        gps_port=args.gps_port,
        simulate=args.simulate,
        enable_vision=not args.no_vision,
        enable_obd=not args.no_obd,
        enable_gps=not args.no_gps,
    )

    service.run(show_ui=args.ui)


if __name__ == "__main__":
    main()
