# test_memory_store.py
import json
import os
import tempfile
import unittest
from unittest.mock import patch
from memory_store import MemoryStore


class TestMemoryStoreAppend(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.store = MemoryStore(base_dir=self.tmpdir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)

    def test_append_creates_signals_file(self):
        entry = {
            "type": "failure",
            "status": "captured",
            "confidence": 1,
            "source": {"hook": "PostToolUseFailure"},
            "content": "Bash: npm test failed",
            "context": "exit code 1",
            "session_id": "test-session",
        }
        result = self.store.append(entry)
        self.assertTrue(os.path.exists(os.path.join(self.tmpdir, "signals.jsonl")))
        self.assertIn("id", result)
        self.assertIn("timestamp", result)
        self.assertEqual(result["version"], 1)

    def test_append_generates_sequential_ids(self):
        entry = {"type": "failure", "status": "captured", "confidence": 1,
                 "source": {"hook": "test"}, "content": "test", "context": "test",
                 "session_id": "s1"}
        r1 = self.store.append(entry)
        r2 = self.store.append(entry)
        # IDs should be different
        self.assertNotEqual(r1["id"], r2["id"])

    def test_get_by_id(self):
        entry = {"type": "correction", "status": "captured", "confidence": 2,
                 "source": {"hook": "PreCompact", "turn": 10},
                 "content": "Use pnpm", "context": "User said no npm",
                 "session_id": "s1"}
        result = self.store.append(entry)
        fetched = self.store.get(result["id"])
        self.assertEqual(fetched["content"], "Use pnpm")
        self.assertEqual(fetched["type"], "correction")

    def test_get_nonexistent_returns_none(self):
        self.assertIsNone(self.store.get("SIG-99999999-9999"))


if __name__ == "__main__":
    unittest.main()
