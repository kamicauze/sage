#!/usr/bin/env python3
"""
OBD-II Reader for Drive Buddy
Reads vehicle data via ELM327 adapter (Bluetooth/USB)

Hardware:
- ELM327 OBD-II adapter (~$15-30)
- Connects via Bluetooth or USB

Install: pip install obd
"""

import os
import time
import json
import threading
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass, asdict

try:
    import obd
    OBD_AVAILABLE = True
except ImportError:
    OBD_AVAILABLE = False
    print("[OBD] Warning: 'obd' module not installed. Run: pip install obd")


@dataclass
class VehicleState:
    """Current vehicle state from OBD-II"""
    timestamp: float = 0
    connected: bool = False

    # Speed & Engine
    speed_kmh: float = 0
    rpm: int = 0
    throttle_percent: float = 0

    # Fuel
    fuel_level_percent: float = 0
    fuel_rate_lph: float = 0  # liters per hour

    # Temperature
    coolant_temp_c: float = 0
    intake_temp_c: float = 0

    # Diagnostics
    engine_load_percent: float = 0
    dtc_codes: list = None  # Diagnostic Trouble Codes
    mil_on: bool = False  # Malfunction Indicator Light (Check Engine)

    def __post_init__(self):
        if self.dtc_codes is None:
            self.dtc_codes = []

    def to_dict(self):
        return asdict(self)


class OBDReader:
    """
    Reads vehicle data from OBD-II port via ELM327 adapter.

    Usage:
        reader = OBDReader(port="/dev/rfcomm0")  # Bluetooth
        reader = OBDReader(port="/dev/ttyUSB0")  # USB
        reader.start()

        state = reader.get_state()
        print(f"Speed: {state.speed_kmh} km/h")
    """

    # OBD commands to poll
    COMMANDS = {
        'speed': obd.commands.SPEED if OBD_AVAILABLE else None,
        'rpm': obd.commands.RPM if OBD_AVAILABLE else None,
        'throttle': obd.commands.THROTTLE_POS if OBD_AVAILABLE else None,
        'fuel_level': obd.commands.FUEL_LEVEL if OBD_AVAILABLE else None,
        'coolant_temp': obd.commands.COOLANT_TEMP if OBD_AVAILABLE else None,
        'intake_temp': obd.commands.INTAKE_TEMP if OBD_AVAILABLE else None,
        'engine_load': obd.commands.ENGINE_LOAD if OBD_AVAILABLE else None,
    }

    def __init__(
        self,
        port: str = "auto",  # "auto", "/dev/rfcomm0", "/dev/ttyUSB0"
        poll_interval: float = 0.5,  # seconds
        on_state_change: Optional[Callable[[VehicleState], None]] = None,
        on_dtc: Optional[Callable[[list], None]] = None,
    ):
        self.port = port
        self.poll_interval = poll_interval
        self.on_state_change = on_state_change
        self.on_dtc = on_dtc

        self.state = VehicleState()
        self.connection = None
        self.running = False
        self.thread = None

    def connect(self) -> bool:
        """Connect to OBD-II adapter"""
        if not OBD_AVAILABLE:
            print("[OBD] Module not available")
            return False

        try:
            if self.port == "auto":
                # Auto-detect port
                self.connection = obd.OBD()
            else:
                self.connection = obd.OBD(self.port)

            if self.connection.is_connected():
                print(f"[OBD] Connected to {self.connection.port_name()}")
                self.state.connected = True
                return True
            else:
                print("[OBD] Failed to connect")
                return False

        except Exception as e:
            print(f"[OBD] Connection error: {e}")
            return False

    def disconnect(self):
        """Disconnect from OBD-II"""
        if self.connection:
            self.connection.close()
            self.connection = None
            self.state.connected = False
            print("[OBD] Disconnected")

    def _poll(self):
        """Poll all OBD commands"""
        if not self.connection or not self.connection.is_connected():
            self.state.connected = False
            return

        self.state.timestamp = time.time()
        self.state.connected = True

        # Speed
        response = self.connection.query(obd.commands.SPEED)
        if not response.is_null():
            self.state.speed_kmh = response.value.magnitude

        # RPM
        response = self.connection.query(obd.commands.RPM)
        if not response.is_null():
            self.state.rpm = int(response.value.magnitude)

        # Throttle
        response = self.connection.query(obd.commands.THROTTLE_POS)
        if not response.is_null():
            self.state.throttle_percent = response.value.magnitude

        # Fuel level
        response = self.connection.query(obd.commands.FUEL_LEVEL)
        if not response.is_null():
            self.state.fuel_level_percent = response.value.magnitude

        # Coolant temp
        response = self.connection.query(obd.commands.COOLANT_TEMP)
        if not response.is_null():
            self.state.coolant_temp_c = response.value.magnitude

        # Engine load
        response = self.connection.query(obd.commands.ENGINE_LOAD)
        if not response.is_null():
            self.state.engine_load_percent = response.value.magnitude

        # Callback
        if self.on_state_change:
            self.on_state_change(self.state)

    def check_dtc(self) -> list:
        """Check for Diagnostic Trouble Codes"""
        if not self.connection or not self.connection.is_connected():
            return []

        try:
            response = self.connection.query(obd.commands.GET_DTC)
            if not response.is_null():
                codes = [str(code) for code in response.value]
                self.state.dtc_codes = codes
                self.state.mil_on = len(codes) > 0

                if codes and self.on_dtc:
                    self.on_dtc(codes)

                return codes
        except:
            pass
        return []

    def _worker(self):
        """Background polling thread"""
        while self.running:
            try:
                self._poll()
            except Exception as e:
                print(f"[OBD] Poll error: {e}")
            time.sleep(self.poll_interval)

    def start(self):
        """Start background polling"""
        if not self.connect():
            return False

        self.running = True
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()
        print(f"[OBD] Polling started (every {self.poll_interval}s)")
        return True

    def stop(self):
        """Stop background polling"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        self.disconnect()

    def get_state(self) -> VehicleState:
        """Get current vehicle state"""
        return self.state


# Simulated OBD for testing without hardware
class SimulatedOBDReader(OBDReader):
    """Simulated OBD reader for testing"""

    def connect(self) -> bool:
        print("[OBD] Using simulated data")
        self.state.connected = True
        return True

    def disconnect(self):
        self.state.connected = False

    def _poll(self):
        import random

        self.state.timestamp = time.time()
        self.state.connected = True

        # Simulate driving
        self.state.speed_kmh = random.uniform(40, 80)
        self.state.rpm = int(random.uniform(1500, 3500))
        self.state.throttle_percent = random.uniform(10, 50)
        self.state.fuel_level_percent = random.uniform(30, 70)
        self.state.coolant_temp_c = random.uniform(85, 95)
        self.state.engine_load_percent = random.uniform(20, 60)

        if self.on_state_change:
            self.on_state_change(self.state)


if __name__ == "__main__":
    # Test with simulated data
    def on_state(state):
        print(f"Speed: {state.speed_kmh:.0f} km/h | RPM: {state.rpm} | Fuel: {state.fuel_level_percent:.0f}%")

    reader = SimulatedOBDReader(poll_interval=1.0, on_state_change=on_state)
    reader.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        reader.stop()
