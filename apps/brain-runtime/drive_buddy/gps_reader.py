#!/usr/bin/env python3
"""
GPS Reader for Drive Buddy
Reads location data from GPS module via serial (NMEA)

Hardware options:
- USB GPS dongle (e.g., VK-162, ~$15)
- UART GPS module (e.g., NEO-6M, NEO-M8N, ~$10-20)
- Phone tethered GPS via gpsd

Install: pip install pynmea2 pyserial
"""

import os
import time
import json
import threading
import math
from typing import Optional, Callable
from dataclasses import dataclass, asdict

try:
    import serial
    import pynmea2
    GPS_AVAILABLE = True
except ImportError:
    GPS_AVAILABLE = False
    print("[GPS] Warning: 'pynmea2' or 'pyserial' not installed. Run: pip install pynmea2 pyserial")


@dataclass
class GPSState:
    """Current GPS state"""
    timestamp: float = 0
    connected: bool = False
    has_fix: bool = False

    # Position
    latitude: float = 0.0
    longitude: float = 0.0
    altitude_m: float = 0.0

    # Movement
    speed_kmh: float = 0.0
    heading: float = 0.0  # degrees, 0=North

    # Quality
    satellites: int = 0
    hdop: float = 99.9  # Horizontal dilution of precision (lower=better)
    fix_quality: int = 0  # 0=invalid, 1=GPS, 2=DGPS

    # Computed
    road_name: str = ""  # From reverse geocoding (optional)

    def to_dict(self):
        return asdict(self)


class GPSReader:
    """
    Reads GPS data from serial NMEA device.

    Usage:
        gps = GPSReader(port="/dev/ttyUSB0")  # USB GPS
        gps = GPSReader(port="/dev/ttyAMA0")  # UART on Pi/Jetson
        gps.start()

        state = gps.get_state()
        print(f"Position: {state.latitude}, {state.longitude}")
    """

    def __init__(
        self,
        port: str = "/dev/ttyUSB0",
        baudrate: int = 9600,
        on_position_change: Optional[Callable[[GPSState], None]] = None,
        on_speed_change: Optional[Callable[[float], None]] = None,
    ):
        self.port = port
        self.baudrate = baudrate
        self.on_position_change = on_position_change
        self.on_speed_change = on_speed_change

        self.state = GPSState()
        self.serial = None
        self.running = False
        self.thread = None

        # For change detection
        self._last_lat = 0
        self._last_lon = 0
        self._last_speed = 0

    def connect(self) -> bool:
        """Connect to GPS serial port"""
        if not GPS_AVAILABLE:
            print("[GPS] Module not available")
            return False

        try:
            self.serial = serial.Serial(
                self.port,
                self.baudrate,
                timeout=1
            )
            print(f"[GPS] Connected to {self.port}")
            self.state.connected = True
            return True

        except Exception as e:
            print(f"[GPS] Connection error: {e}")
            return False

    def disconnect(self):
        """Disconnect from GPS"""
        if self.serial:
            self.serial.close()
            self.serial = None
            self.state.connected = False
            print("[GPS] Disconnected")

    def _parse_nmea(self, line: str):
        """Parse NMEA sentence"""
        try:
            msg = pynmea2.parse(line)

            # GGA - Fix data
            if isinstance(msg, pynmea2.GGA):
                self.state.latitude = msg.latitude if msg.latitude else 0
                self.state.longitude = msg.longitude if msg.longitude else 0
                self.state.altitude_m = float(msg.altitude) if msg.altitude else 0
                self.state.satellites = int(msg.num_sats) if msg.num_sats else 0
                self.state.hdop = float(msg.horizontal_dil) if msg.horizontal_dil else 99.9
                self.state.fix_quality = int(msg.gps_qual) if msg.gps_qual else 0
                self.state.has_fix = self.state.fix_quality > 0

            # RMC - Recommended minimum
            elif isinstance(msg, pynmea2.RMC):
                if msg.status == 'A':  # Active/valid
                    self.state.latitude = msg.latitude if msg.latitude else self.state.latitude
                    self.state.longitude = msg.longitude if msg.longitude else self.state.longitude
                    self.state.speed_kmh = float(msg.spd_over_grnd) * 1.852 if msg.spd_over_grnd else 0
                    self.state.heading = float(msg.true_course) if msg.true_course else 0
                    self.state.has_fix = True

            # VTG - Course and speed
            elif isinstance(msg, pynmea2.VTG):
                if msg.spd_over_grnd_kmph:
                    self.state.speed_kmh = float(msg.spd_over_grnd_kmph)
                if msg.true_track:
                    self.state.heading = float(msg.true_track)

            self.state.timestamp = time.time()

            # Check for significant changes
            self._check_changes()

        except pynmea2.ParseError:
            pass
        except Exception as e:
            pass  # Ignore parse errors

    def _check_changes(self):
        """Check for significant position/speed changes and trigger callbacks"""
        # Position change (more than ~10 meters)
        if self.on_position_change:
            dist = self._haversine(
                self._last_lat, self._last_lon,
                self.state.latitude, self.state.longitude
            )
            if dist > 0.01:  # 10 meters
                self._last_lat = self.state.latitude
                self._last_lon = self.state.longitude
                self.on_position_change(self.state)

        # Speed change (more than 5 km/h)
        if self.on_speed_change:
            if abs(self.state.speed_kmh - self._last_speed) > 5:
                self._last_speed = self.state.speed_kmh
                self.on_speed_change(self.state.speed_kmh)

    def _haversine(self, lat1, lon1, lat2, lon2) -> float:
        """Calculate distance between two points in km"""
        R = 6371  # Earth radius in km
        dLat = math.radians(lat2 - lat1)
        dLon = math.radians(lon2 - lon1)
        a = (math.sin(dLat/2) ** 2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
             math.sin(dLon/2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        return R * c

    def _worker(self):
        """Background reading thread"""
        while self.running:
            try:
                if self.serial and self.serial.in_waiting:
                    line = self.serial.readline().decode('ascii', errors='ignore').strip()
                    if line.startswith('$'):
                        self._parse_nmea(line)
            except Exception as e:
                print(f"[GPS] Read error: {e}")
            time.sleep(0.1)

    def start(self):
        """Start background reading"""
        if not self.connect():
            return False

        self.running = True
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()
        print("[GPS] Reading started")
        return True

    def stop(self):
        """Stop background reading"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        self.disconnect()

    def get_state(self) -> GPSState:
        """Get current GPS state"""
        return self.state

    def get_speed_limit(self) -> Optional[int]:
        """
        Get speed limit for current location.
        Would require external API (OpenStreetMap, HERE, etc.)
        """
        # TODO: Implement with OSM Overpass API or HERE API
        return None


# Simulated GPS for testing
class SimulatedGPSReader(GPSReader):
    """Simulated GPS for testing without hardware"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Simulate driving in Nairobi
        self._sim_lat = -1.2921  # Nairobi
        self._sim_lon = 36.8219
        self._sim_heading = 45  # NE

    def connect(self) -> bool:
        print("[GPS] Using simulated data")
        self.state.connected = True
        return True

    def disconnect(self):
        self.state.connected = False

    def _worker(self):
        import random

        while self.running:
            # Simulate movement
            speed = random.uniform(30, 80)
            self._sim_lat += random.uniform(-0.0001, 0.0001)
            self._sim_lon += random.uniform(-0.0001, 0.0001)
            self._sim_heading = (self._sim_heading + random.uniform(-5, 5)) % 360

            self.state.timestamp = time.time()
            self.state.has_fix = True
            self.state.latitude = self._sim_lat
            self.state.longitude = self._sim_lon
            self.state.altitude_m = 1700  # Nairobi altitude
            self.state.speed_kmh = speed
            self.state.heading = self._sim_heading
            self.state.satellites = random.randint(6, 12)
            self.state.hdop = random.uniform(0.8, 2.0)
            self.state.fix_quality = 1

            self._check_changes()
            time.sleep(1)


if __name__ == "__main__":
    def on_position(state):
        print(f"Position: {state.latitude:.6f}, {state.longitude:.6f} | "
              f"Speed: {state.speed_kmh:.0f} km/h | Heading: {state.heading:.0f}°")

    gps = SimulatedGPSReader(on_position_change=on_position)
    gps.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        gps.stop()
