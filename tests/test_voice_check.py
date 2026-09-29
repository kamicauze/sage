import os
import sys
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from brain.voice.voice_check import (  # noqa: E402
    grade,
    parser_agrees,
    summarize_stt,
    summarize_tts,
    word_error_rate,
)


class WerTests(unittest.TestCase):
    def test_exact_and_case_punctuation_insensitive(self):
        self.assertEqual(word_error_rate("turn on the lamp", "Turn on the lamp."), 0.0)

    def test_substitution_insertion_deletion(self):
        self.assertAlmostEqual(word_error_rate("turn on the lamp", "turn on the lab"), 0.25)
        self.assertAlmostEqual(word_error_rate("turn on the lamp", "turn on the desk lamp"), 0.25)
        self.assertAlmostEqual(word_error_rate("turn on the lamp", "turn the lamp"), 0.25)

    def test_empty_cases(self):
        self.assertEqual(word_error_rate("", ""), 0.0)
        self.assertEqual(word_error_rate("", "hello"), 1.0)
        self.assertEqual(word_error_rate("hello there", ""), 1.0)

    def test_grades(self):
        self.assertEqual(grade(0), "perfect")
        self.assertEqual(grade(0.2), "good")
        self.assertEqual(grade(0.5), "rough")
        self.assertEqual(grade(0.9), "bad")


class ParserAgreementTests(unittest.TestCase):
    def test_slip_that_still_parses_counts_as_ok(self):
        self.assertTrue(parser_agrees("turn on the desk lamp", "turn on the desk lamp."))
        self.assertTrue(parser_agrees("switch off the fan", "switch of the fan"))

    def test_wrong_device_is_not_ok(self):
        self.assertFalse(parser_agrees("turn on the desk lamp", "turn on the fan"))

    def test_lost_command_is_not_ok(self):
        self.assertFalse(parser_agrees("lights off", "lights"))

    def test_non_command_phrases_agree_when_both_ignored(self):
        self.assertTrue(parser_agrees("what time is it", "what time is it now"))


class SummaryTests(unittest.TestCase):
    def test_stt_summary(self):
        s = summarize_stt([
            {"expected": "a", "heard": "a", "wer": 0.0, "transcribe_ms": 100, "parser_ok": True},
            {"expected": "b", "heard": "c", "wer": 1.0, "transcribe_ms": 300, "parser_ok": False},
            {"expected": "d", "heard": None, "wer": None, "transcribe_ms": None, "parser_ok": None},
        ])
        self.assertEqual((s["phrases"], s["heard"], s["missed"], s["perfect"]), (3, 2, 1, 1))
        self.assertEqual(s["mean_wer"], 0.5)
        self.assertEqual((s["parser_ok"], s["parser_total"]), (1, 2))
        self.assertEqual(s["median_transcribe_ms"], 200)

    def test_tts_summary(self):
        s = summarize_tts([
            {"text": "x", "first_audio_ms": 400, "gen_ms": 300, "audio_s": 1.5, "engine": "kokoro"},
            {"text": "y", "first_audio_ms": None},
        ])
        self.assertEqual((s["spoken"], s["failed"], s["engine"]), (1, 1, "kokoro"))
        self.assertEqual(s["median_first_audio_ms"], 400)
        self.assertEqual(s["mean_realtime_factor"], 0.2)

    def test_empty_summaries(self):
        self.assertIsNone(summarize_stt([])["mean_wer"])
        self.assertIsNone(summarize_tts([])["median_gen_ms"])


if __name__ == "__main__":
    unittest.main()
