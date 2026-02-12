# test_capture_signals.py
import json
import os
import tempfile
import unittest
from capture_signals import extract_signals_from_transcript


class TestCorrectionDetection(unittest.TestCase):
    def test_detects_no_correction(self):
        transcript = [
            {"role": "assistant", "content": "I'll use npm to install."},
            {"role": "user", "content": "No, use pnpm not npm in this project"},
        ]
        signals = extract_signals_from_transcript(transcript, "test-sess")
        corrections = [s for s in signals if s["type"] == "correction"]
        self.assertGreaterEqual(len(corrections), 1)
        self.assertIn("pnpm", corrections[0]["context"])

    def test_detects_actually_correction(self):
        transcript = [
            {"role": "assistant", "content": "The config is in /opt."},
            {"role": "user", "content": "Actually, the config file is in /etc"},
        ]
        signals = extract_signals_from_transcript(transcript, "test-sess")
        corrections = [s for s in signals if s["type"] == "correction"]
        self.assertGreaterEqual(len(corrections), 1)

    def test_detects_workflow_correction_high_confidence(self):
        transcript = [
            {"role": "assistant", "content": "Running grep to search."},
            {"role": "user", "content": "Use rg instead of grep, it's faster"},
        ]
        signals = extract_signals_from_transcript(transcript, "test-sess")
        corrections = [s for s in signals if s["type"] == "correction"]
        self.assertGreaterEqual(len(corrections), 1)
        # Workflow corrections should be high confidence
        self.assertGreaterEqual(corrections[0]["confidence"], 3)


class TestConventionDetection(unittest.TestCase):
    def test_detects_explicit_convention(self):
        transcript = [
            {"role": "user", "content": "We always use absolute imports in this project"},
        ]
        signals = extract_signals_from_transcript(transcript, "test-sess")
        conventions = [s for s in signals if s["type"] == "convention"]
        self.assertGreaterEqual(len(conventions), 1)

    def test_detects_naming_convention(self):
        transcript = [
            {"role": "user", "content": "Our naming convention is camelCase for files"},
        ]
        signals = extract_signals_from_transcript(transcript, "test-sess")
        conventions = [s for s in signals if s["type"] == "convention"]
        self.assertGreaterEqual(len(conventions), 1)


class TestFailureDetection(unittest.TestCase):
    def test_detects_repeated_failures(self):
        transcript = [
            {"role": "assistant", "tool_use": {"name": "Bash", "error": "exit 1"}},
            {"role": "assistant", "tool_use": {"name": "Bash", "error": "exit 1"}},
        ]
        signals = extract_signals_from_transcript(transcript, "test-sess")
        failures = [s for s in signals if s["type"] == "failure"]
        self.assertGreaterEqual(len(failures), 1)


class TestCommandDetection(unittest.TestCase):
    def test_detects_backtick_command(self):
        transcript = [
            {"role": "user", "content": "Run `pnpm test:unit` to run the tests"},
        ]
        signals = extract_signals_from_transcript(transcript, "test-sess")
        commands = [s for s in signals if s["type"] == "command"]
        self.assertGreaterEqual(len(commands), 1)
        self.assertIn("pnpm test:unit", commands[0]["content"])


class TestPositiveReinforcementDetection(unittest.TestCase):
    def test_detects_strong_positive(self):
        transcript = [
            {"role": "assistant", "content": "I've refactored the auth module."},
            {"role": "user", "content": "Perfect, that's exactly what I wanted"},
        ]
        signals = extract_signals_from_transcript(transcript, "test-sess")
        patterns = [s for s in signals if s["type"] == "pattern"]
        self.assertGreaterEqual(len(patterns), 1)


if __name__ == "__main__":
    unittest.main()
