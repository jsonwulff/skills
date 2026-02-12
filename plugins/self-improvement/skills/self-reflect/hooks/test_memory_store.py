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


class TestMemoryStoreQuery(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.store = MemoryStore(base_dir=self.tmpdir)
        # Seed test data
        self.store.append({"type": "failure", "status": "captured", "confidence": 1,
                           "source": {"hook": "PostToolUseFailure"}, "content": "npm failed",
                           "context": "exit 1", "session_id": "s1"})
        self.store.append({"type": "correction", "status": "captured", "confidence": 2,
                           "source": {"hook": "PreCompact"}, "content": "Use pnpm",
                           "context": "User said no npm", "session_id": "s1",
                           "tags": ["package-manager"]})
        self.store.append({"type": "convention", "status": "analyzed", "confidence": 2,
                           "source": {"hook": "PreCompact"}, "content": "camelCase files",
                           "context": "convention observed", "session_id": "s2"})

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)

    def test_query_by_status(self):
        results = self.store.query(status="captured")
        self.assertEqual(len(results), 2)

    def test_query_by_type(self):
        results = self.store.query(entry_type="correction")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["content"], "Use pnpm")

    def test_query_by_session(self):
        results = self.store.query(session_id="s2")
        self.assertEqual(len(results), 1)

    def test_query_by_tags(self):
        results = self.store.query(tags=["package-manager"])
        self.assertEqual(len(results), 1)

    def test_query_combined_filters(self):
        results = self.store.query(status="captured", entry_type="failure")
        self.assertEqual(len(results), 1)

    def test_query_no_matches(self):
        results = self.store.query(status="promoted")
        self.assertEqual(len(results), 0)


class TestMemoryStoreUpdate(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.store = MemoryStore(base_dir=self.tmpdir)
        result = self.store.append({"type": "failure", "status": "captured", "confidence": 1,
                                     "source": {"hook": "test"}, "content": "test fail",
                                     "context": "ctx", "session_id": "s1"})
        self.entry_id = result["id"]

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)

    def test_update_status(self):
        updated = self.store.update(self.entry_id, {"status": "analyzed"})
        self.assertEqual(updated["status"], "analyzed")
        # Verify persistence
        fetched = self.store.get(self.entry_id)
        self.assertEqual(fetched["status"], "analyzed")

    def test_update_confidence(self):
        updated = self.store.update(self.entry_id, {"confidence": 3})
        self.assertEqual(updated["confidence"], 3)

    def test_update_nonexistent_returns_none(self):
        self.assertIsNone(self.store.update("SIG-99999999-0001", {"status": "analyzed"}))


class TestMemoryStoreArchive(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.store = MemoryStore(base_dir=self.tmpdir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)

    def test_archive_removes_old_entries(self):
        # Manually write an old entry
        old_ts = "2026-01-01T00:00:00Z"
        old_entry = {"id": "SIG-20260101-0001", "version": 1, "timestamp": old_ts,
                     "session_id": "old", "type": "failure", "status": "captured",
                     "confidence": 1, "source": {"hook": "test"}, "content": "old",
                     "context": "old", "category": "", "tags": [], "related": [],
                     "promoted_to": None, "meta": {}}
        os.makedirs(self.tmpdir, exist_ok=True)
        with open(self.store.signals_path, "w") as f:
            f.write(json.dumps(old_entry) + "\n")
        # Add a recent entry
        self.store.append({"type": "failure", "status": "captured", "confidence": 1,
                           "source": {"hook": "test"}, "content": "new",
                           "context": "new", "session_id": "s1"})
        removed = self.store.archive(days=14)
        self.assertEqual(removed, 1)
        remaining = self.store.query()
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0]["content"], "new")


class TestMemoryStoreStats(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.store = MemoryStore(base_dir=self.tmpdir)
        self.store.append({"type": "failure", "status": "captured", "confidence": 1,
                           "source": {"hook": "test"}, "content": "f1", "context": "c",
                           "session_id": "s1"})
        self.store.append({"type": "correction", "status": "captured", "confidence": 2,
                           "source": {"hook": "test"}, "content": "c1", "context": "c",
                           "session_id": "s1"})
        self.store.append({"type": "correction", "status": "promoted", "confidence": 4,
                           "source": {"hook": "test"}, "content": "c2", "context": "c",
                           "session_id": "s1"})

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)

    def test_stats_counts(self):
        s = self.store.stats()
        self.assertEqual(s["total"], 3)
        self.assertEqual(s["by_status"]["captured"], 2)
        self.assertEqual(s["by_status"]["promoted"], 1)
        self.assertEqual(s["by_type"]["failure"], 1)
        self.assertEqual(s["by_type"]["correction"], 2)

    def test_stats_statusline_format(self):
        line = self.store.stats(fmt="statusline")
        # Should be a compact string like "reflect: 2 pending"
        self.assertIn("2", line)


class TestMemoryStorePromote(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.store = MemoryStore(base_dir=self.tmpdir)
        result = self.store.append({"type": "correction", "status": "captured", "confidence": 2,
                                     "source": {"hook": "PreCompact"}, "content": "Use pnpm",
                                     "context": "User said no", "session_id": "s1",
                                     "category": "command"})
        self.entry_id = result["id"]

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)

    def test_promote_updates_status_and_target(self):
        promoted = self.store.promote(self.entry_id, "~/.claude/CLAUDE.md", "Use pnpm not npm")
        self.assertEqual(promoted["status"], "promoted")
        self.assertEqual(promoted["promoted_to"], "~/.claude/CLAUDE.md")

    def test_promote_creates_learnings_index(self):
        self.store.promote(self.entry_id, "~/.claude/CLAUDE.md", "Use pnpm not npm")
        self.assertTrue(os.path.exists(self.store.learnings_index))
        with open(self.store.learnings_index, "r") as f:
            content = f.read()
        self.assertIn("Use pnpm not npm", content)
        self.assertIn(self.entry_id.replace("SIG", "LRN"), content)


if __name__ == "__main__":
    unittest.main()
