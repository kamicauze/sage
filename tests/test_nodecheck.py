import os
import sys
import time
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from brain.cluster.nodecheck import (  # noqa: E402
    ROLES,
    Report,
    format_node_table,
    host_from_url,
    is_local_host,
    pick_dongles,
    z2m_mqtt_server,
)


class HelperTests(unittest.TestCase):
    def test_is_local_host(self):
        self.assertTrue(is_local_host("localhost"))
        self.assertTrue(is_local_host("127.0.0.1"))
        self.assertTrue(is_local_host("192.168.1.10", ["192.168.1.10"]))
        self.assertFalse(is_local_host("192.168.1.10", ["192.168.1.50"]))

    def test_z2m_mqtt_server(self):
        cfg = """homeassistant: false
permit_join: false
mqtt:
  base_topic: zigbee2mqtt
  server: 'mqtt://192.168.1.10:1883'   # the Mini
serial:
  port: /dev/ttyUSB0
"""
        self.assertEqual(z2m_mqtt_server(cfg), "mqtt://192.168.1.10:1883")
        self.assertIsNone(z2m_mqtt_server("serial:\n  port: /dev/ttyUSB0\n"))
        # a "server:" under another section must not be picked up
        self.assertIsNone(z2m_mqtt_server("frontend:\n  server: 0.0.0.0\nmqtt:\n  base_topic: z\n"))

    def test_host_from_url(self):
        self.assertEqual(host_from_url("mqtt://192.168.1.10:1883"), "192.168.1.10")
        self.assertEqual(host_from_url("mqtt://localhost"), "localhost")
        self.assertEqual(host_from_url("mini.local"), "mini.local")

    def test_pick_dongles_prefers_named_by_id(self):
        paths = ["/dev/ttyUSB0", "/dev/ttyAMA0",
                 "/dev/serial/by-id/usb-ITead_Sonoff_Zigbee_3.0_USB_Dongle_Plus_abc-if00-port0"]
        self.assertEqual(pick_dongles(paths), [paths[2]])
        self.assertEqual(pick_dongles(["/dev/ttyUSB0", "/dev/ttyAMA0"]), ["/dev/ttyUSB0"])
        self.assertEqual(pick_dongles(["/dev/ttyAMA0"]), [])


class ReportTests(unittest.TestCase):
    def test_summary_and_result(self):
        r = Report(role="vision", host="orin")
        r.add("PASS", "a")
        r.add("WARN", "b")
        self.assertFalse(r.failed)
        self.assertEqual(r.summary()["result"], "WARN")
        r.add("FAIL", "camera 0 gives no frames", "try VISION_CAMERA=1")
        s = r.summary()
        self.assertTrue(r.failed)
        self.assertEqual(s["result"], "FAIL")
        self.assertEqual(s["counts"], {"PASS": 1, "WARN": 1, "FAIL": 1})
        self.assertEqual(s["failures"], ["camera 0 gives no frames: try VISION_CAMERA=1"])

    def test_node_table(self):
        now = time.time()
        table = format_node_table([
            {"host": "mini", "role": "hub", "result": "PASS", "ts": now - 30, "failures": []},
            {"host": "orin", "role": "vision", "result": "FAIL", "ts": now - 600, "failures": ["Ollama not reachable"]},
        ], now=now)
        self.assertIn("mini", table)
        self.assertIn("10m", table)
        self.assertIn("Ollama not reachable", table)
        self.assertIn("No report yet from: home, voice", table)
        self.assertIn("No node reports", format_node_table([]))

    def test_roles(self):
        self.assertEqual(set(ROLES), {"hub", "home", "voice", "vision"})


if __name__ == "__main__":
    unittest.main()
