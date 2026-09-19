"""
Voice -> switch loop tests. No MQTT broker, no audio, no models: the controller and the
simulated node talk through an in-memory bus, exactly the way they talk through Mosquitto.
"""
import json
import os
import sys
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from brain.devices.switch_commands import (  # noqa: E402
    Switch,
    SwitchRegistry,
    normalize_text,
    parse_switch_command,
    spoken_reply,
    strip_wake_word,
)
from brain.devices.switch_controller import SwitchController, summarize_z2m_devices  # noqa: E402
from brain.devices.switch_node import SimBackend, SwitchNode  # noqa: E402


class FakeBus:
    """Records publishes; can replay them into subscribers like a broker would."""

    def __init__(self):
        self.messages = []

    def publish(self, topic, payload, retain=False):
        self.messages.append((topic, payload))

    def topic(self, topic):
        return [p for t, p in self.messages if t == topic]

    def clear(self):
        self.messages.clear()


def panel_registry():
    return SwitchRegistry.from_data({
        "zigbee2mqtt_base": "zigbee2mqtt",
        "switches": [
            {"id": "l1", "name": "main light", "aliases": ["big light", "office light"], "group": "lights",
             "room": "office", "zigbee_name": "office_panel", "state_key": "state_l1"},
            {"id": "l2", "name": "desk lamp", "aliases": ["lamp"], "group": "lights",
             "room": "office", "zigbee_name": "office_panel", "state_key": "state_l2"},
            {"id": "fan", "name": "fan", "group": "fans", "room": "office",
             "zigbee_name": "office_panel", "state_key": "state_l3"},
            {"id": "kitchen_light", "name": "kitchen light", "aliases": ["kitchen"], "group": "lights",
             "room": "kitchen"},  # plain "sage" protocol (sim / gpio node)
        ],
    })


class RegistryTests(unittest.TestCase):
    def test_default_registry_file_loads(self):
        reg = SwitchRegistry.load()
        self.assertGreater(len(reg), 0)
        for s in reg:
            self.assertTrue(s.command_topic)
            self.assertTrue(s.state_topic)

    def test_zigbee_switch_topics_and_payloads(self):
        s = Switch(id="x", name="x", zigbee_name="office_panel", state_key="state_l2", protocol="zigbee2mqtt")
        self.assertEqual(s.command_topic, "zigbee2mqtt/office_panel/set")
        self.assertEqual(s.state_topic, "zigbee2mqtt/office_panel")
        self.assertEqual(s.get_topic, "zigbee2mqtt/office_panel/get")
        self.assertEqual(json.loads(s.payload_for("on")), {"state_l2": "ON"})
        self.assertEqual(json.loads(s.payload_for("off")), {"state_l2": "OFF"})
        self.assertEqual(json.loads(s.payload_for("toggle")), {"state_l2": "TOGGLE"})

    def test_zigbee_state_parsing_reads_only_its_gang(self):
        s = Switch(id="x", name="x", zigbee_name="p", state_key="state_l2", protocol="zigbee2mqtt")
        self.assertEqual(s.parse_state('{"state_l1": "ON", "state_l2": "OFF", "linkquality": 120}'), "off")
        self.assertIsNone(s.parse_state('{"state_l1": "ON"}'))
        self.assertIsNone(s.parse_state("ON"))

    def test_plain_switch_defaults(self):
        s = Switch(id="kitchen_light", name="kitchen light")
        self.assertEqual(s.command_topic, "sage/switch/kitchen_light/set")
        self.assertEqual(s.payload_for("on"), "ON")
        self.assertEqual(s.parse_state("OFF"), "off")
        self.assertEqual(s.parse_state('{"state": "on"}'), "on")

    def test_zigbee_name_implies_protocol(self):
        reg = panel_registry()
        self.assertTrue(reg.get("l1").is_zigbee)
        self.assertFalse(reg.get("kitchen_light").is_zigbee)

    def test_custom_base_topic(self):
        reg = SwitchRegistry.from_data({"zigbee2mqtt_base": "z2m", "switches": [
            {"id": "a", "name": "a", "zigbee_name": "dev"}]})
        self.assertEqual(reg.get("a").command_topic, "z2m/dev/set")


class ParserTests(unittest.TestCase):
    def setUp(self):
        self.reg = panel_registry()

    def parse(self, text):
        return parse_switch_command(text, self.reg)

    def assert_cmd(self, text, action, ids):
        cmd = self.parse(text)
        self.assertIsNotNone(cmd, f"expected a command for {text!r}")
        self.assertEqual(cmd.action, action, text)
        self.assertEqual([s.id for s in cmd.switches], ids, text)

    def test_basic_on_off(self):
        self.assert_cmd("turn on the desk lamp", "on", ["l2"])
        self.assert_cmd("Turn the lamp off.", "off", ["l2"])
        self.assert_cmd("switch on the big light", "on", ["l1"])
        self.assert_cmd("put the fan on", "on", ["fan"])
        self.assert_cmd("kill the fan", "off", ["fan"])

    def test_tight_forms_without_verb(self):
        self.assert_cmd("lamp on", "on", ["l2"])
        self.assert_cmd("fan off", "off", ["fan"])

    def test_stt_slips(self):
        self.assert_cmd("turn of the lamp", "off", ["l2"])
        self.assert_cmd("lights of", "off", ["l1", "l2", "kitchen_light"])
        self.assert_cmd("TURN ON THE FAN!!", "on", ["fan"])

    def test_groups_rooms_and_all(self):
        self.assert_cmd("lights off", "off", ["l1", "l2", "kitchen_light"])
        self.assert_cmd("office lights off", "off", ["l1", "l2"])
        self.assert_cmd("turn on the kitchen lights", "on", ["kitchen_light"])
        self.assert_cmd("switch off everything", "off", ["l1", "l2", "fan", "kitchen_light"])
        self.assert_cmd("all lights on", "on", ["l1", "l2", "kitchen_light"])

    def test_multiple_targets(self):
        self.assert_cmd("turn off the fan and the lamp", "off", ["fan", "l2"])

    def test_toggle_and_status(self):
        self.assert_cmd("toggle the lamp", "toggle", ["l2"])
        self.assert_cmd("is the fan on", "status", ["fan"])
        self.assert_cmd("are the lights on", "status", ["l1", "l2", "kitchen_light"])

    def test_longest_alias_wins(self):
        # "kitchen light" must not also match the bare "kitchen" alias twice or "light" group.
        self.assert_cmd("turn on the kitchen light", "on", ["kitchen_light"])

    def test_ordinary_speech_is_ignored(self):
        for text in [
            "I'm on my way to the kitchen",
            "what's the weather",
            "the fan",
            "kitchen",
            "I left the lamp at the office",
            "",
            "   ",
        ]:
            self.assertIsNone(self.parse(text), text)

    def test_spoken_replies(self):
        self.assertEqual(spoken_reply(self.parse("turn on the lamp")), "Desk lamp on.")
        self.assertEqual(spoken_reply(self.parse("lights off")), "Lights off.")
        self.assertEqual(spoken_reply(self.parse("switch off everything")), "All off.")
        self.assertEqual(spoken_reply(self.parse("toggle the fan")), "Toggled fan.")
        self.assertEqual(spoken_reply(self.parse("is the fan on"), {"fan": "on"}), "Fan is on.")
        self.assertEqual(spoken_reply(self.parse("is the fan on"), {}), "Fan is unknown.")
        self.assertEqual(spoken_reply(self.parse("are the office lights on"), {"l1": "on"}),
                         "Main light is on. Desk lamp is unknown.")

    def test_wake_word(self):
        self.assertEqual(strip_wake_word("Hey Sage, turn on the lamp", "sage"), "turn on the lamp")
        self.assertEqual(strip_wake_word("sage lamp off", "sage"), "lamp off")
        self.assertIsNone(strip_wake_word("turn on the lamp", "sage"))
        self.assertEqual(strip_wake_word("turn on the lamp", ""), "turn on the lamp")

    def test_normalize(self):
        self.assertEqual(normalize_text("  Turn ON, the Lamp!  "), "turn on the lamp")


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.reg = panel_registry()
        self.bus = FakeBus()
        self.ctl = SwitchController(self.reg, client=self.bus)

    def test_command_publishes_zigbee_json_and_spoken_reply(self):
        cmd = self.ctl.handle_transcript("turn on the desk lamp")
        self.assertEqual(cmd.action, "on")
        self.assertEqual(self.bus.topic("zigbee2mqtt/office_panel/set"), ['{"state_l2": "ON"}'])
        reply = json.loads(self.bus.topic("sage/voice/response")[0])
        self.assertEqual(reply["text"], "Desk lamp on.")
        self.assertEqual(reply["source"], "switch_controller")
        event = json.loads(self.bus.topic("sage/switch/events")[0])
        self.assertEqual(event["event"], "command")
        self.assertEqual(event["applied"], [{"id": "l2", "state": "on"}])

    def test_plain_switch_publishes_plain_payload(self):
        self.ctl.handle_transcript("kitchen light off")
        self.assertEqual(self.bus.topic("sage/switch/kitchen_light/set"), ["OFF"])

    def test_group_command_merges_gangs_into_one_panel_message(self):
        self.ctl.handle_transcript("office lights off")
        msgs = self.bus.topic("zigbee2mqtt/office_panel/set")
        self.assertEqual(len(msgs), 1)
        self.assertEqual(json.loads(msgs[0]), {"state_l1": "OFF", "state_l2": "OFF"})

    def test_everything_off_touches_panel_once_and_plain_switch_separately(self):
        self.ctl.handle_transcript("switch off everything")
        self.assertEqual(json.loads(self.bus.topic("zigbee2mqtt/office_panel/set")[0]),
                         {"state_l1": "OFF", "state_l2": "OFF", "state_l3": "OFF"})
        self.assertEqual(self.bus.topic("sage/switch/kitchen_light/set"), ["OFF"])

    def test_no_match_is_silent_by_default(self):
        self.assertIsNone(self.ctl.handle_transcript("what's the weather like"))
        self.assertEqual(self.bus.topic("sage/voice/response"), [])
        self.assertEqual(json.loads(self.bus.topic("sage/switch/events")[0])["event"], "no_match")

    def test_no_match_can_reply(self):
        ctl = SwitchController(self.reg, client=self.bus, reply_unknown=True)
        ctl.handle_transcript("what's the weather like")
        self.assertIn("did not catch", json.loads(self.bus.topic("sage/voice/response")[0])["text"])

    def test_speak_false_skips_tts(self):
        ctl = SwitchController(self.reg, client=self.bus, speak=False)
        ctl.handle_transcript("lamp on")
        self.assertEqual(self.bus.topic("sage/voice/response"), [])
        self.assertEqual(len(self.bus.topic("zigbee2mqtt/office_panel/set")), 1)

    def test_wake_word_gate(self):
        ctl = SwitchController(self.reg, client=self.bus, wake_word="sage")
        self.assertIsNone(ctl.handle_transcript("turn on the lamp"))
        self.assertIsNotNone(ctl.handle_transcript("hey sage turn on the lamp"))

    def test_transcript_payload_forms(self):
        self.assertEqual(SwitchController.extract_text(b"lamp on"), "lamp on")
        self.assertEqual(SwitchController.extract_text('{"text": "lamp on"}'), "lamp on")
        self.assertEqual(SwitchController.extract_text(""), "")

    def test_state_tracking_from_panel_json(self):
        changes = self.ctl.record_state("zigbee2mqtt/office_panel", '{"state_l1": "ON", "state_l3": "OFF"}')
        self.assertEqual(changes, {"l1": "on", "fan": "off"})
        self.assertEqual(self.ctl.states, {"l1": "on", "fan": "off"})
        self.assertEqual(self.ctl.record_state("zigbee2mqtt/other", '{"state": "ON"}'), {})

    def test_status_uses_tracked_state(self):
        self.ctl.record_state("zigbee2mqtt/office_panel", '{"state_l3": "ON"}')
        self.ctl.handle_transcript("is the fan on")
        self.assertEqual(json.loads(self.bus.topic("sage/voice/response")[-1])["text"], "Fan is on.")
        self.assertEqual(self.bus.topic("zigbee2mqtt/office_panel/set"), [])  # status never flips anything

    def test_zigbee_toggle_is_native(self):
        self.ctl.handle_transcript("toggle the fan")
        self.assertEqual(self.bus.topic("zigbee2mqtt/office_panel/set"), ['{"state_l3": "TOGGLE"}'])

    def test_plain_toggle_computed_from_state(self):
        self.ctl.record_state("sage/switch/kitchen_light/state", "ON")
        self.ctl.handle_transcript("toggle the kitchen light")
        self.assertEqual(self.bus.topic("sage/switch/kitchen_light/set"), ["OFF"])

    def test_request_states_asks_each_panel_once(self):
        self.ctl.request_states()
        gets = self.bus.topic("zigbee2mqtt/office_panel/get")
        self.assertEqual(len(gets), 1)
        self.assertEqual(json.loads(gets[0]), {"state_l1": "", "state_l2": "", "state_l3": ""})


class NodeTests(unittest.TestCase):
    def setUp(self):
        self.reg = panel_registry()
        self.bus = FakeBus()
        self.node = SwitchNode(self.reg, SimBackend(self.reg), client=self.bus)

    def test_zigbee_command_updates_only_that_gang_and_reports_full_panel(self):
        touched = self.node.handle_command("zigbee2mqtt/office_panel/set", '{"state_l2": "ON"}')
        self.assertEqual(touched, {"l2": "on"})
        state = json.loads(self.bus.topic("zigbee2mqtt/office_panel")[-1])
        self.assertEqual(state, {"state_l1": "OFF", "state_l2": "ON", "state_l3": "OFF"})

    def test_zigbee_toggle(self):
        self.node.handle_command("zigbee2mqtt/office_panel/set", '{"state_l3": "TOGGLE"}')
        self.assertEqual(self.node.states["fan"], "on")
        self.node.handle_command("zigbee2mqtt/office_panel/set", '{"state_l3": "TOGGLE"}')
        self.assertEqual(self.node.states["fan"], "off")

    def test_plain_command(self):
        self.assertEqual(self.node.handle_command("sage/switch/kitchen_light/set", b"ON"), {"kitchen_light": "on"})
        self.assertEqual(self.bus.topic("sage/switch/kitchen_light/state")[-1], "ON")

    def test_unknown_topic_and_bad_payload(self):
        self.assertEqual(self.node.handle_command("zigbee2mqtt/nope/set", '{"state": "ON"}'), {})
        self.assertEqual(self.node.handle_command("zigbee2mqtt/office_panel/set", "garbage"), {})


class EndToEndLoopTests(unittest.TestCase):
    """Transcript -> controller -> (bus) -> node -> (bus) -> controller state, no broker needed."""

    def setUp(self):
        self.reg = panel_registry()
        self.bus = FakeBus()
        self.ctl = SwitchController(self.reg, client=self.bus)
        self.node = SwitchNode(self.reg, SimBackend(self.reg), client=self.bus)

    def pump(self):
        """Deliver every queued message to whoever subscribes to it, like a broker would."""
        pending = list(self.bus.messages)
        self.bus.clear()
        for topic, payload in pending:
            if topic.endswith("/set"):
                self.node.handle_command(topic, payload)
            elif self.reg.by_state_topic(topic):
                self.ctl.record_state(topic, payload)

    def test_voice_turn_flips_panel_and_state_comes_back(self):
        self.ctl.handle_transcript("turn on the fan")
        self.pump()   # controller -> node
        self.assertEqual(self.node.states["fan"], "on")
        self.pump()   # node state -> controller
        self.assertEqual(self.ctl.states["fan"], "on")

        self.ctl.handle_transcript("is the fan on")
        self.assertEqual(json.loads(self.bus.topic("sage/voice/response")[-1])["text"], "Fan is on.")

        self.ctl.handle_transcript("switch off everything")
        self.pump()
        self.assertEqual(set(self.node.states.values()), {"off"})


class DiscoverTests(unittest.TestCase):
    def test_summarize_bridge_devices(self):
        devices = [
            {"type": "Coordinator", "friendly_name": "Coordinator"},
            {"type": "Router", "friendly_name": "office_panel", "model_id": "TS0013",
             "definition": {"model": "TS0013", "description": "3 gang switch", "exposes": [
                 {"type": "switch", "endpoint": "l1", "features": [{"type": "binary", "property": "state_l1"}]},
                 {"type": "switch", "endpoint": "l2", "features": [{"type": "binary", "property": "state_l2"}]},
                 {"type": "switch", "endpoint": "l3", "features": [{"type": "binary", "property": "state_l3"}]},
                 {"type": "numeric", "property": "linkquality"},
             ]}},
            {"type": "EndDevice", "friendly_name": "plug", "definition": {"model": "X", "exposes": [
                {"type": "switch", "features": [{"type": "binary", "property": "state"}]}]}},
        ]
        rows = summarize_z2m_devices(devices)
        self.assertEqual([r["friendly_name"] for r in rows], ["office_panel", "plug"])
        self.assertEqual(rows[0]["switch_keys"], ["state_l1", "state_l2", "state_l3"])
        self.assertEqual(rows[1]["switch_keys"], ["state"])


if __name__ == "__main__":
    unittest.main()
