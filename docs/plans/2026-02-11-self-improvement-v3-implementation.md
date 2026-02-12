# Self-Improvement v3 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement the v3 memory-driven self-improvement system with hook-based signal capture, JSONL memory store, dual-scope `/reflect` skill, and `/reflect-toggle` hook management.

**Architecture:** Hooks capture signals silently during work (PreCompact transcript mining, PostToolUseFailure logging, SessionEnd summaries). Signals flow through a 3-layer storage system (ephemeral JSONL → intermediate learnings → promoted CLAUDE.md/improvements.md). A shared `memory_store.py` module abstracts all storage operations. `/reflect` analyzes signals one-at-a-time FIFO and proposes improvements. `/reflect-toggle` manages hooks in `settings.json`.

**Tech Stack:** Python 3 (stdlib only), Bash, JSONL, Markdown. No external dependencies.

**Design doc:** `docs/plans/2026-02-11-self-improvement-v3-design.md`

---

### Task 1: memory_store.py — Core storage module

The foundation. Every hook and skill depends on this module. It abstracts JSONL read/write operations and provides both a Python API and CLI interface.

**Files:**
- Create: `plugins/self-improvement/skills/self-reflect/hooks/memory_store.py`
- Create: `plugins/self-improvement/skills/self-reflect/hooks/test_memory_store.py`

**Step 1: Write failing tests for `append()` and `get()`**

```python
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
```

**Step 2: Run tests to verify they fail**

Run: `cd plugins/self-improvement/skills/self-reflect/hooks && python3 -m pytest test_memory_store.py -v`
Expected: FAIL — `memory_store` module does not exist.

**Step 3: Implement `MemoryStore` with `append()` and `get()`**

```python
# memory_store.py
"""
Shared storage abstraction for the self-improvement v3 system.
Manages signals.jsonl (ephemeral captures) and learnings/ (analyzed entries).
Usable as Python module or CLI: python3 memory_store.py <command> [args]
"""
import json
import os
import sys
from datetime import datetime, timezone


SIGNALS_FILE = "signals.jsonl"
LEARNINGS_DIR = "learnings"
LEARNINGS_INDEX = "LEARNINGS.md"
DEFAULT_BASE_DIR = os.path.expanduser("~/.claude/reflections")


class MemoryStore:
    def __init__(self, base_dir=None):
        self.base_dir = base_dir or DEFAULT_BASE_DIR
        self.signals_path = os.path.join(self.base_dir, SIGNALS_FILE)
        self.learnings_dir = os.path.join(self.base_dir, LEARNINGS_DIR)
        self.learnings_index = os.path.join(self.learnings_dir, LEARNINGS_INDEX)

    def _ensure_dir(self):
        os.makedirs(self.base_dir, exist_ok=True)

    def _ensure_learnings_dir(self):
        os.makedirs(self.learnings_dir, exist_ok=True)

    def _next_id(self):
        """Generate SIG-YYYYMMDD-NNNN id based on today's date and sequence."""
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        prefix = f"SIG-{today}-"
        max_seq = 0
        if os.path.exists(self.signals_path):
            with open(self.signals_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        eid = entry.get("id", "")
                        if eid.startswith(prefix):
                            seq = int(eid[len(prefix):])
                            max_seq = max(max_seq, seq)
                    except (json.JSONDecodeError, ValueError):
                        continue
        return f"{prefix}{max_seq + 1:04d}"

    def append(self, entry):
        """Append a signal entry to signals.jsonl. Returns the complete entry with generated fields."""
        self._ensure_dir()
        now = datetime.now(timezone.utc)
        complete = {
            "id": self._next_id(),
            "version": 1,
            "timestamp": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
            **entry,
            "category": entry.get("category", ""),
            "tags": entry.get("tags", []),
            "related": entry.get("related", []),
            "promoted_to": entry.get("promoted_to", None),
            "meta": entry.get("meta", {}),
        }
        # Prune old entries on append (14-day TTL)
        self._prune_if_needed()
        with open(self.signals_path, "a") as f:
            f.write(json.dumps(complete) + "\n")
        return complete

    def get(self, entry_id):
        """Fetch a single entry by ID. Returns None if not found."""
        if not os.path.exists(self.signals_path):
            return None
        with open(self.signals_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("id") == entry_id:
                        return entry
                except json.JSONDecodeError:
                    continue
        return None

    def _prune_if_needed(self):
        """Remove entries older than 14 days. Runs opportunistically."""
        if not os.path.exists(self.signals_path):
            return
        # Only prune every ~50 appends (check file size as proxy)
        try:
            size = os.path.getsize(self.signals_path)
            if size < 50000:  # ~50KB, skip pruning for small files
                return
        except OSError:
            return
        self.archive(days=14)

    def archive(self, days=14, status_filter=None):
        """Remove entries older than `days` days, optionally filtered by status."""
        pass  # Implemented in Task 2

    def query(self, status=None, entry_type=None, since=None, tags=None, session_id=None):
        """Filter signals. Returns list of matching entries."""
        pass  # Implemented in Task 2

    def update(self, entry_id, fields):
        """Update fields on an existing entry. Returns updated entry or None."""
        pass  # Implemented in Task 2

    def stats(self, fmt=None):
        """Return counts by status, type, category."""
        pass  # Implemented in Task 2

    def promote(self, entry_id, target, content):
        """Mark entry as promoted, record target, add to learnings index."""
        pass  # Implemented in Task 2
```

**Step 4: Run tests to verify they pass**

Run: `cd plugins/self-improvement/skills/self-reflect/hooks && python3 -m pytest test_memory_store.py -v`
Expected: All 4 tests PASS.

**Step 5: Commit**

```bash
git add plugins/self-improvement/skills/self-reflect/hooks/memory_store.py \
       plugins/self-improvement/skills/self-reflect/hooks/test_memory_store.py
git commit -m "feat(self-improvement): add memory_store.py with append/get operations"
```

---

### Task 2: memory_store.py — query, update, archive, stats, promote

Complete the remaining `MemoryStore` methods.

**Files:**
- Modify: `plugins/self-improvement/skills/self-reflect/hooks/memory_store.py`
- Modify: `plugins/self-improvement/skills/self-reflect/hooks/test_memory_store.py`

**Step 1: Write failing tests**

```python
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
```

**Step 2: Run tests to verify they fail**

Run: `cd plugins/self-improvement/skills/self-reflect/hooks && python3 -m pytest test_memory_store.py -v`
Expected: New tests FAIL (methods return None or are stubs).

**Step 3: Implement `query()`, `update()`, `archive()`, `stats()`, `promote()`**

```python
    # Add these methods to MemoryStore class:

    def _read_all(self):
        """Read all entries from signals.jsonl."""
        entries = []
        if not os.path.exists(self.signals_path):
            return entries
        with open(self.signals_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return entries

    def _write_all(self, entries):
        """Overwrite signals.jsonl with the given entries."""
        self._ensure_dir()
        with open(self.signals_path, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")

    def query(self, status=None, entry_type=None, since=None, tags=None, session_id=None):
        """Filter signals. Returns list of matching entries, oldest first."""
        entries = self._read_all()
        results = []
        for e in entries:
            if status and e.get("status") != status:
                continue
            if entry_type and e.get("type") != entry_type:
                continue
            if session_id and e.get("session_id") != session_id:
                continue
            if tags:
                entry_tags = e.get("tags", [])
                if not any(t in entry_tags for t in tags):
                    continue
            if since:
                entry_ts = e.get("timestamp", "")
                if entry_ts < since:
                    continue
            results.append(e)
        return results

    def update(self, entry_id, fields):
        """Update fields on an existing entry. Rewrites the file. Returns updated entry or None."""
        entries = self._read_all()
        updated = None
        for i, e in enumerate(entries):
            if e.get("id") == entry_id:
                entries[i] = {**e, **fields}
                updated = entries[i]
                break
        if updated is None:
            return None
        self._write_all(entries)
        return updated

    def archive(self, days=14, status_filter=None):
        """Remove entries older than `days` days. Returns count of removed entries."""
        entries = self._read_all()
        cutoff = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        # Calculate cutoff timestamp
        from datetime import timedelta
        cutoff_dt = datetime.now(timezone.utc) - timedelta(days=days)
        cutoff_ts = cutoff_dt.isoformat(timespec="seconds").replace("+00:00", "Z")

        keep = []
        removed = 0
        for e in entries:
            ts = e.get("timestamp", "")
            status = e.get("status", "")
            # Never prune confirmed/promoted entries
            if status in ("promoted", "confirmed"):
                keep.append(e)
                continue
            if status_filter and status != status_filter:
                keep.append(e)
                continue
            if ts < cutoff_ts:
                removed += 1
            else:
                keep.append(e)
        if removed > 0:
            self._write_all(keep)
        return removed

    def stats(self, fmt=None):
        """Return counts by status, type, category. If fmt='statusline', return compact string."""
        entries = self._read_all()
        by_status = {}
        by_type = {}
        by_category = {}
        for e in entries:
            s = e.get("status", "unknown")
            t = e.get("type", "unknown")
            c = e.get("category", "unknown")
            by_status[s] = by_status.get(s, 0) + 1
            by_type[t] = by_type.get(t, 0) + 1
            by_category[c] = by_category.get(c, 0) + 1

        result = {
            "total": len(entries),
            "by_status": by_status,
            "by_type": by_type,
            "by_category": by_category,
        }
        if fmt == "statusline":
            pending = by_status.get("captured", 0) + by_status.get("analyzed", 0)
            if pending == 0:
                return ""
            return f"reflect: {pending} pending"
        return result

    def promote(self, entry_id, target, content):
        """Mark entry as promoted, record target, add to learnings index."""
        updated = self.update(entry_id, {"status": "promoted", "promoted_to": target})
        if updated is None:
            return None
        # Write to learnings index
        self._ensure_learnings_dir()
        lrn_id = updated["id"].replace("SIG", "LRN")
        category = updated.get("category", "General")
        category_title = category.replace("-", " ").replace("_", " ").title() if category else "General"

        # Read or create learnings index
        if os.path.exists(self.learnings_index):
            with open(self.learnings_index, "r") as f:
                index_content = f.read()
        else:
            index_content = "# Learnings\n"

        # Find or create category section
        section_header = f"## {category_title}"
        if section_header not in index_content:
            index_content = index_content.rstrip() + f"\n\n{section_header}\n"

        # Append entry under section
        entry_line = f"- [{lrn_id}] {content} (promoted to {target})\n"
        # Insert after section header
        pos = index_content.index(section_header) + len(section_header)
        # Find next section or end
        next_section = index_content.find("\n## ", pos)
        if next_section == -1:
            index_content = index_content.rstrip() + "\n" + entry_line
        else:
            index_content = index_content[:next_section].rstrip() + "\n" + entry_line + index_content[next_section:]

        with open(self.learnings_index, "w") as f:
            f.write(index_content)

        return updated
```

**Step 4: Run tests to verify they pass**

Run: `cd plugins/self-improvement/skills/self-reflect/hooks && python3 -m pytest test_memory_store.py -v`
Expected: All tests PASS.

**Step 5: Commit**

```bash
git add plugins/self-improvement/skills/self-reflect/hooks/memory_store.py \
       plugins/self-improvement/skills/self-reflect/hooks/test_memory_store.py
git commit -m "feat(self-improvement): add query/update/archive/stats/promote to memory_store"
```

---

### Task 3: memory_store.py — CLI interface

Add a `__main__` block so hooks can call `python3 memory_store.py <command> [args]`.

**Files:**
- Modify: `plugins/self-improvement/skills/self-reflect/hooks/memory_store.py`
- Modify: `plugins/self-improvement/skills/self-reflect/hooks/test_memory_store.py`

**Step 1: Write failing tests**

```python
class TestMemoryStoreCLI(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.script = os.path.join(os.path.dirname(__file__), "memory_store.py")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)

    def _run(self, *args):
        import subprocess
        env = os.environ.copy()
        env["REFLECTIONS_DIR"] = self.tmpdir
        result = subprocess.run(
            ["python3", self.script] + list(args),
            capture_output=True, text=True, env=env
        )
        return result

    def test_cli_append(self):
        entry_json = json.dumps({
            "type": "failure", "status": "captured", "confidence": 1,
            "source": {"hook": "test"}, "content": "cli test",
            "context": "ctx", "session_id": "s1"
        })
        result = self._run("append", entry_json)
        self.assertEqual(result.returncode, 0)
        output = json.loads(result.stdout)
        self.assertIn("id", output)

    def test_cli_stats(self):
        # Append something first
        entry_json = json.dumps({
            "type": "failure", "status": "captured", "confidence": 1,
            "source": {"hook": "test"}, "content": "test",
            "context": "ctx", "session_id": "s1"
        })
        self._run("append", entry_json)
        result = self._run("stats")
        self.assertEqual(result.returncode, 0)
        output = json.loads(result.stdout)
        self.assertEqual(output["total"], 1)

    def test_cli_stats_statusline(self):
        entry_json = json.dumps({
            "type": "failure", "status": "captured", "confidence": 1,
            "source": {"hook": "test"}, "content": "test",
            "context": "ctx", "session_id": "s1"
        })
        self._run("append", entry_json)
        result = self._run("stats", "--format", "statusline")
        self.assertEqual(result.returncode, 0)
        self.assertIn("1 pending", result.stdout)

    def test_cli_query(self):
        entry_json = json.dumps({
            "type": "failure", "status": "captured", "confidence": 1,
            "source": {"hook": "test"}, "content": "test",
            "context": "ctx", "session_id": "s1"
        })
        self._run("append", entry_json)
        result = self._run("query", "--status", "captured")
        self.assertEqual(result.returncode, 0)
        output = json.loads(result.stdout)
        self.assertEqual(len(output), 1)
```

**Step 2: Run tests to verify they fail**

Run: `cd plugins/self-improvement/skills/self-reflect/hooks && python3 -m pytest test_memory_store.py::TestMemoryStoreCLI -v`
Expected: FAIL — no CLI interface yet.

**Step 3: Add CLI interface**

Add to the bottom of `memory_store.py`:

```python
def main():
    import argparse

    parser = argparse.ArgumentParser(description="Memory store CLI for self-improvement signals")
    parser.add_argument("command", choices=["append", "query", "get", "update", "stats", "archive"])

    # Allow remaining args for subcommands
    args, remaining = parser.parse_known_args()

    base_dir = os.environ.get("REFLECTIONS_DIR", DEFAULT_BASE_DIR)
    store = MemoryStore(base_dir=base_dir)

    if args.command == "append":
        if not remaining:
            print("Error: append requires a JSON string argument", file=sys.stderr)
            sys.exit(1)
        entry = json.loads(remaining[0])
        result = store.append(entry)
        print(json.dumps(result))

    elif args.command == "query":
        qparser = argparse.ArgumentParser()
        qparser.add_argument("--status")
        qparser.add_argument("--type")
        qparser.add_argument("--session")
        qparser.add_argument("--since")
        qparser.add_argument("--tags", nargs="*")
        qargs = qparser.parse_args(remaining)
        results = store.query(
            status=qargs.status, entry_type=qargs.type,
            session_id=qargs.session, since=qargs.since, tags=qargs.tags
        )
        print(json.dumps(results))

    elif args.command == "get":
        if not remaining:
            print("Error: get requires an entry ID", file=sys.stderr)
            sys.exit(1)
        result = store.get(remaining[0])
        print(json.dumps(result))

    elif args.command == "update":
        uparser = argparse.ArgumentParser()
        uparser.add_argument("entry_id")
        uparser.add_argument("fields_json")
        uargs = uparser.parse_args(remaining)
        fields = json.loads(uargs.fields_json)
        result = store.update(uargs.entry_id, fields)
        print(json.dumps(result))

    elif args.command == "stats":
        sparser = argparse.ArgumentParser()
        sparser.add_argument("--format", dest="fmt")
        sargs = sparser.parse_args(remaining)
        result = store.stats(fmt=sargs.fmt)
        if isinstance(result, str):
            print(result)
        else:
            print(json.dumps(result))

    elif args.command == "archive":
        aparser = argparse.ArgumentParser()
        aparser.add_argument("--days", type=int, default=14)
        aparser.add_argument("--status")
        aargs = aparser.parse_args(remaining)
        removed = store.archive(days=aargs.days, status_filter=aargs.status)
        print(json.dumps({"removed": removed}))


if __name__ == "__main__":
    main()
```

**Step 4: Run all tests**

Run: `cd plugins/self-improvement/skills/self-reflect/hooks && python3 -m pytest test_memory_store.py -v`
Expected: All tests PASS.

**Step 5: Commit**

```bash
git add plugins/self-improvement/skills/self-reflect/hooks/memory_store.py \
       plugins/self-improvement/skills/self-reflect/hooks/test_memory_store.py
git commit -m "feat(self-improvement): add CLI interface to memory_store.py"
```

---

### Task 4: capture-failure.sh — PostToolUseFailure hook

Simplest hook. Validates the hook → memory_store pipeline end-to-end.

**Files:**
- Create: `plugins/self-improvement/skills/self-reflect/hooks/capture-failure.sh`

**Step 1: Write the hook script**

```bash
#!/usr/bin/env bash
# capture-failure.sh — PostToolUseFailure hook (async, 5s timeout)
# Appends tool failure signals to signals.jsonl via memory_store.py.

set -euo pipefail

HOOK_DIR="$(cd "$(dirname "$0")" && pwd)"
MEMORY_STORE="$HOOK_DIR/memory_store.py"

# Check python3 availability
if ! command -v python3 &>/dev/null; then
    echo '{"hookSpecificOutput":{"hookEventName":"PostToolUseFailure","additionalContext":"Self-improvement hooks require Python 3 but it was not found. Signal capture is disabled. Install Python 3 or run /reflect-toggle to disable hooks."}}' >&2
    exit 0
fi

# Read hook input from stdin
INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_name','unknown'))" 2>/dev/null || echo "unknown")
ERROR=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('error','')[:200])" 2>/dev/null || echo "")
SESSION_ID=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('session_id',''))" 2>/dev/null || echo "")

# Skip if we couldn't extract meaningful data
if [ -z "$ERROR" ] && [ "$TOOL_NAME" = "unknown" ]; then
    exit 0
fi

ENTRY=$(python3 -c "
import json
print(json.dumps({
    'type': 'failure',
    'status': 'captured',
    'confidence': 1,
    'source': {'hook': 'PostToolUseFailure'},
    'content': '$TOOL_NAME failed: $(echo "$ERROR" | head -c 100 | tr -d "'" | tr -d '"')',
    'context': '$(echo "$ERROR" | head -c 200 | tr -d "'" | tr -d '"')',
    'session_id': '$SESSION_ID',
    'category': '',
    'tags': ['$TOOL_NAME']
}))
")

python3 "$MEMORY_STORE" append "$ENTRY" >/dev/null 2>&1

exit 0
```

**Step 2: Make executable and test manually**

Run: `chmod +x plugins/self-improvement/skills/self-reflect/hooks/capture-failure.sh`

Test with mock input:
```bash
echo '{"tool_name":"Bash","error":"npm test: command not found","session_id":"test-123"}' | \
  REFLECTIONS_DIR=/tmp/test-reflections \
  bash plugins/self-improvement/skills/self-reflect/hooks/capture-failure.sh && \
  cat /tmp/test-reflections/signals.jsonl
```
Expected: One JSONL entry with type "failure" and content about npm test.

**Step 3: Clean up test data and commit**

```bash
rm -rf /tmp/test-reflections
git add plugins/self-improvement/skills/self-reflect/hooks/capture-failure.sh
git commit -m "feat(self-improvement): add PostToolUseFailure hook script"
```

---

### Task 5: inject-signals.sh — SessionStart(compact) hook

Reads signals for the current session and injects a compact summary as `additionalContext` after compaction.

**Files:**
- Create: `plugins/self-improvement/skills/self-reflect/hooks/inject-signals.sh`

**Step 1: Write the hook script**

```bash
#!/usr/bin/env bash
# inject-signals.sh — SessionStart hook (matcher: "compact")
# After compaction, injects captured signals as additionalContext
# so they survive in the post-compaction context.

set -euo pipefail

HOOK_DIR="$(cd "$(dirname "$0")" && pwd)"
MEMORY_STORE="$HOOK_DIR/memory_store.py"

# Check dependencies
if ! command -v python3 &>/dev/null; then
    echo '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"Self-improvement hooks require Python 3 but it was not found. Signal capture is disabled. Install Python 3 or run /reflect-toggle to disable hooks."}}'
    exit 0
fi

if ! command -v jq &>/dev/null; then
    echo '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"Self-improvement hooks require jq but it was not found. Run `brew install jq` (macOS) or `apt install jq` (Linux) to enable full signal capture."}}'
    exit 0
fi

# Read hook input from stdin
INPUT=$(cat)
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // empty')

if [ -z "$SESSION_ID" ]; then
    exit 0
fi

# Query signals for current session
SIGNALS=$(python3 "$MEMORY_STORE" query --status captured --session "$SESSION_ID" 2>/dev/null || echo "[]")

# Check if there are any signals
COUNT=$(echo "$SIGNALS" | jq 'length')
if [ "$COUNT" = "0" ] || [ -z "$COUNT" ]; then
    exit 0
fi

# Format compact summary
SUMMARY=$(echo "$SIGNALS" | python3 -c "
import sys, json
signals = json.load(sys.stdin)
lines = []
for s in signals[-20:]:  # Last 20 signals max
    t = s.get('type', '?')
    c = s.get('content', '')[:80]
    lines.append(f'- [{t}] {c}')
print('Self-improvement signals captured before compaction:')
print('\n'.join(lines))
print('\nRun /reflect to review and persist these learnings.')
")

# Output additionalContext JSON
jq -n --arg ctx "$SUMMARY" '{
    hookSpecificOutput: {
        hookEventName: "SessionStart",
        additionalContext: $ctx
    }
}'
```

**Step 2: Test manually**

```bash
chmod +x plugins/self-improvement/skills/self-reflect/hooks/inject-signals.sh

# Seed a signal first
REFLECTIONS_DIR=/tmp/test-reflections python3 plugins/self-improvement/skills/self-reflect/hooks/memory_store.py append '{"type":"correction","status":"captured","confidence":2,"source":{"hook":"PreCompact"},"content":"Use pnpm not npm","context":"user correction","session_id":"test-sess"}'

# Run the inject hook
echo '{"session_id":"test-sess","source":"compact"}' | \
  REFLECTIONS_DIR=/tmp/test-reflections \
  bash plugins/self-improvement/skills/self-reflect/hooks/inject-signals.sh
```

Expected: JSON output with `hookSpecificOutput.additionalContext` containing the signal summary.

**Step 3: Test empty case**

```bash
echo '{"session_id":"no-signals","source":"compact"}' | \
  REFLECTIONS_DIR=/tmp/test-reflections \
  bash plugins/self-improvement/skills/self-reflect/hooks/inject-signals.sh
```

Expected: No output (exit 0 silently).

**Step 4: Clean up and commit**

```bash
rm -rf /tmp/test-reflections
git add plugins/self-improvement/skills/self-reflect/hooks/inject-signals.sh
git commit -m "feat(self-improvement): add SessionStart(compact) context injection hook"
```

---

### Task 6: capture-signals.py — PreCompact hook

The most complex hook. Reads the transcript JSONL and applies heuristic pattern matching to extract learning signals.

**Files:**
- Create: `plugins/self-improvement/skills/self-reflect/hooks/capture-signals.py`
- Create: `plugins/self-improvement/skills/self-reflect/hooks/test_capture_signals.py`

**Step 1: Write failing tests for heuristic detection**

```python
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
```

**Step 2: Run tests to verify they fail**

Run: `cd plugins/self-improvement/skills/self-reflect/hooks && python3 -m pytest test_capture_signals.py -v`
Expected: FAIL — module does not exist.

**Step 3: Implement capture-signals.py**

```python
#!/usr/bin/env python3
"""
capture-signals.py — PreCompact hook for self-improvement v3.
Reads the transcript JSONL and extracts learning signal candidates
using keyword heuristics. Writes to signals.jsonl via memory_store.

Hook type: command (synchronous)
Timeout: 30 seconds
Stdin: JSON with session_id, transcript_path, cwd, hook_event_name
"""

import json
import os
import re
import sys

# Import memory_store from same directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from memory_store import MemoryStore


# --- Heuristic keyword sets ---

CORRECTION_KEYWORDS = [
    r"\bno,\s", r"\bnope\b", r"\bwrong\b", r"\bincorrect\b",
    r"that's not right", r"not quite",
    r"\bactually[,\s]", r"\binstead\b", r"\brather\b",
    r"should be\b", r"supposed to be", r"meant to\b", r"I meant\b",
    r"don't use\b", r"stop using\b", r"switch to\b",
    r"prefer \w+ over", r"we don't do that",
    r"that's outdated", r"that changed", r"not anymore", r"\bdeprecated\b",
]

WORKFLOW_CORRECTION_PATTERN = re.compile(
    r"use\s+(\w+)\s+instead\s+of\s+(\w+)", re.IGNORECASE
)

CONVENTION_KEYWORDS = [
    r"always use\b", r"never use\b", r"we prefer\b",
    r"our convention", r"our standard", r"the convention is", r"the pattern is",
    r"in this project", r"in this repo", r"in this codebase",
    r"around here", r"on this team",
    r"naming convention", r"file structure", r"folder structure",
    r"we put \w+ in", r"\w+ goes? in\b", r"we keep \w+ in",
    r"we follow\b", r"we stick to\b", r"house rule", r"code style", r"our approach",
]

POSITIVE_STRONG = [
    r"\bperfect\b", r"\bexactly\b", r"exactly right", r"that's it\b",
    r"nailed it", r"spot on", r"love it",
]

POSITIVE_MODERATE = [
    r"\bgreat\b", r"\bnice\b", r"looks good", r"that works\b",
    r"that's correct", r"yes that's right", r"good approach",
    r"\bawesome\b", r"\bbrilliant\b", r"\bexcellent\b",
    r"well done", r"much better",
]

COMMAND_PATTERN = re.compile(r"`([^`]+)`")


def _matches_any(text, patterns):
    """Check if text matches any regex pattern (case-insensitive)."""
    text_lower = text.lower()
    for pattern in patterns:
        if re.search(pattern, text_lower):
            return True
    return False


def _extract_user_messages(transcript):
    """Extract (index, message_text) pairs for user messages from transcript entries."""
    messages = []
    for i, entry in enumerate(transcript):
        role = entry.get("role", "")
        if role == "user":
            content = entry.get("content", "")
            if isinstance(content, list):
                # Handle structured content blocks
                text_parts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
                content = " ".join(text_parts)
            if content:
                messages.append((i, content))
    return messages


def _is_after_assistant_action(transcript, user_index):
    """Check if the user message at user_index follows a substantive assistant action."""
    for j in range(user_index - 1, max(user_index - 5, -1), -1):
        if j < 0:
            break
        entry = transcript[j]
        if entry.get("role") == "assistant":
            # Check for tool use or substantial content
            if entry.get("tool_use") or len(entry.get("content", "")) > 50:
                return True
    return False


def _detect_repeated_failures(transcript):
    """Detect same tool failing 2+ times consecutively."""
    failures = []
    consecutive = []
    for entry in transcript:
        tool = entry.get("tool_use", {})
        if isinstance(tool, dict) and tool.get("error"):
            name = tool.get("name", "unknown")
            if consecutive and consecutive[-1]["name"] == name:
                consecutive.append({"name": name, "error": tool["error"]})
            else:
                if len(consecutive) >= 2:
                    failures.append(consecutive)
                consecutive = [{"name": name, "error": tool["error"]}]
        else:
            if len(consecutive) >= 2:
                failures.append(consecutive)
            consecutive = []
    if len(consecutive) >= 2:
        failures.append(consecutive)
    return failures


def _detect_search_thrashing(transcript):
    """Detect 3+ Glob/Grep with empty results before finding target."""
    empty_searches = 0
    for entry in transcript:
        tool = entry.get("tool_use", {})
        if isinstance(tool, dict):
            name = tool.get("name", "")
            if name in ("Glob", "Grep"):
                result = tool.get("result", "")
                if not result or result.strip() == "[]" or "No matches" in str(result):
                    empty_searches += 1
                else:
                    if empty_searches >= 3:
                        return True
                    empty_searches = 0
            else:
                if empty_searches >= 3:
                    return True
                empty_searches = 0
    return empty_searches >= 3


def extract_signals_from_transcript(transcript, session_id):
    """Main extraction function. Returns list of signal dicts (without id/timestamp — memory_store adds those)."""
    signals = []
    user_messages = _extract_user_messages(transcript)

    for idx, (i, text) in enumerate(user_messages):
        turn = i

        # --- Corrections ---
        if _matches_any(text, CORRECTION_KEYWORDS):
            confidence = 2
            # Check for workflow correction (higher confidence)
            if WORKFLOW_CORRECTION_PATTERN.search(text):
                confidence = 3
            signals.append({
                "type": "correction",
                "status": "captured",
                "confidence": confidence,
                "source": {"hook": "PreCompact", "turn": turn},
                "content": text[:200],
                "context": text[:500],
                "session_id": session_id,
            })

        # --- Conventions ---
        if _matches_any(text, CONVENTION_KEYWORDS):
            signals.append({
                "type": "convention",
                "status": "captured",
                "confidence": 2,
                "source": {"hook": "PreCompact", "turn": turn},
                "content": text[:200],
                "context": text[:500],
                "session_id": session_id,
            })

        # --- Commands ---
        commands_found = COMMAND_PATTERN.findall(text)
        if commands_found and re.search(r"\brun\b", text, re.IGNORECASE):
            for cmd in commands_found[:3]:  # Max 3 commands per message
                signals.append({
                    "type": "command",
                    "status": "captured",
                    "confidence": 2,
                    "source": {"hook": "PreCompact", "turn": turn},
                    "content": cmd,
                    "context": text[:500],
                    "session_id": session_id,
                })

        # --- Positive reinforcement (only after assistant action) ---
        if _is_after_assistant_action(transcript, i):
            if _matches_any(text, POSITIVE_STRONG):
                signals.append({
                    "type": "pattern",
                    "status": "captured",
                    "confidence": 1,
                    "source": {"hook": "PreCompact", "turn": turn},
                    "content": f"Positive reinforcement: {text[:150]}",
                    "context": text[:500],
                    "session_id": session_id,
                })
            elif _matches_any(text, POSITIVE_MODERATE):
                signals.append({
                    "type": "pattern",
                    "status": "captured",
                    "confidence": 1,
                    "source": {"hook": "PreCompact", "turn": turn},
                    "content": f"Positive reinforcement: {text[:150]}",
                    "context": text[:500],
                    "session_id": session_id,
                })

    # --- Repeated failures ---
    for failure_group in _detect_repeated_failures(transcript):
        name = failure_group[0]["name"]
        count = len(failure_group)
        error = failure_group[0].get("error", "")[:200]
        signals.append({
            "type": "failure",
            "status": "captured",
            "confidence": 2,
            "source": {"hook": "PreCompact"},
            "content": f"{name} failed {count} times consecutively: {error[:100]}",
            "context": error,
            "session_id": session_id,
            "tags": [name],
        })

    # --- Search thrashing ---
    if _detect_search_thrashing(transcript):
        signals.append({
            "type": "project_friction",
            "status": "captured",
            "confidence": 1,
            "source": {"hook": "PreCompact"},
            "content": "Multiple search attempts before finding target — possible structural confusion",
            "context": "3+ Glob/Grep calls with empty results before locating the file",
            "session_id": session_id,
        })

    return signals


def read_transcript(path, max_turns=200):
    """Read transcript JSONL file, returning last max_turns entries."""
    entries = []
    if not os.path.exists(path):
        return entries
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries[-max_turns:]


def main():
    # Check python3 — if we got here, python3 exists
    # Read stdin for hook input
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    session_id = hook_input.get("session_id", "")
    transcript_path = hook_input.get("transcript_path", "")

    if not transcript_path or not session_id:
        sys.exit(0)

    transcript = read_transcript(transcript_path)
    if not transcript:
        sys.exit(0)

    signals = extract_signals_from_transcript(transcript, session_id)
    if not signals:
        sys.exit(0)

    store = MemoryStore()
    for signal in signals:
        store.append(signal)

    sys.exit(0)


if __name__ == "__main__":
    main()
```

**Step 4: Run tests**

Run: `cd plugins/self-improvement/skills/self-reflect/hooks && python3 -m pytest test_capture_signals.py -v`
Expected: All tests PASS.

**Step 5: Commit**

```bash
git add plugins/self-improvement/skills/self-reflect/hooks/capture-signals.py \
       plugins/self-improvement/skills/self-reflect/hooks/test_capture_signals.py
git commit -m "feat(self-improvement): add PreCompact transcript mining hook"
```

---

### Task 7: capture-session-summary.py — SessionEnd hook

Extracts a lightweight session summary: files touched, tools used, turn count.

**Files:**
- Create: `plugins/self-improvement/skills/self-reflect/hooks/capture-session-summary.py`

**Step 1: Write the hook script**

```python
#!/usr/bin/env python3
"""
capture-session-summary.py — SessionEnd hook for self-improvement v3.
Extracts a lightweight session summary from the transcript.

Hook type: command (synchronous)
Timeout: 30 seconds
Stdin: JSON with session_id, transcript_path, reason
"""

import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from memory_store import MemoryStore


def extract_summary(transcript):
    """Extract session metadata from transcript entries."""
    tools_used = Counter()
    files_touched = set()
    turn_count = 0

    for entry in transcript:
        role = entry.get("role", "")
        if role in ("user", "assistant"):
            turn_count += 1

        tool = entry.get("tool_use", {})
        if isinstance(tool, dict) and tool.get("name"):
            tools_used[tool["name"]] += 1
            # Track files from Read, Edit, Write, Glob
            tool_input = tool.get("input", {})
            if isinstance(tool_input, dict):
                for key in ("file_path", "path", "file"):
                    if key in tool_input and tool_input[key]:
                        files_touched.add(tool_input[key])

    return {
        "turn_count": turn_count,
        "tools_used": dict(tools_used.most_common(10)),
        "files_touched": sorted(files_touched)[:20],  # Cap at 20
    }


def main():
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    session_id = hook_input.get("session_id", "")
    transcript_path = hook_input.get("transcript_path", "")

    if not transcript_path or not session_id:
        sys.exit(0)

    if not os.path.exists(transcript_path):
        sys.exit(0)

    # Read transcript
    entries = []
    with open(transcript_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    if not entries:
        sys.exit(0)

    summary = extract_summary(entries)

    # Format summary content
    tools_str = ", ".join(f"{k}({v})" for k, v in summary["tools_used"].items())
    files_str = ", ".join(summary["files_touched"][:5])
    if len(summary["files_touched"]) > 5:
        files_str += f" (+{len(summary['files_touched']) - 5} more)"

    content = f"Session: {summary['turn_count']} turns. Tools: {tools_str}. Files: {files_str}"

    store = MemoryStore()
    store.append({
        "type": "summary",
        "status": "captured",
        "confidence": 1,
        "source": {"hook": "SessionEnd"},
        "content": content,
        "context": json.dumps(summary),
        "session_id": session_id,
        "meta": summary,
    })

    sys.exit(0)


if __name__ == "__main__":
    main()
```

**Step 2: Test manually**

Create a mock transcript file and test:
```bash
# Create mock transcript
echo '{"role":"user","content":"Fix the auth bug"}' > /tmp/test-transcript.jsonl
echo '{"role":"assistant","content":"Looking at the code","tool_use":{"name":"Read","input":{"file_path":"src/auth.py"}}}' >> /tmp/test-transcript.jsonl
echo '{"role":"assistant","content":"Found it","tool_use":{"name":"Edit","input":{"file_path":"src/auth.py"}}}' >> /tmp/test-transcript.jsonl

echo '{"session_id":"test-end","transcript_path":"/tmp/test-transcript.jsonl","reason":"logout"}' | \
  REFLECTIONS_DIR=/tmp/test-reflections \
  python3 plugins/self-improvement/skills/self-reflect/hooks/capture-session-summary.py

cat /tmp/test-reflections/signals.jsonl
```

Expected: One JSONL entry with type "summary" containing turn count, tools, and files.

**Step 3: Clean up and commit**

```bash
rm -rf /tmp/test-reflections /tmp/test-transcript.jsonl
git add plugins/self-improvement/skills/self-reflect/hooks/capture-session-summary.py
git commit -m "feat(self-improvement): add SessionEnd session summary hook"
```

---

### Task 8: /reflect-toggle SKILL.md — Hook management skill

Rewrite the toggle skill to manage hooks in `settings.json`.

**Files:**
- Modify: `plugins/self-improvement/skills/self-reflect-toggle/SKILL.md`

**Step 1: Write the new SKILL.md**

```markdown
---
name: self-reflect-toggle
description: "Use when the user invokes /reflect-toggle to enable or disable the self-improvement signal capture system. Toggles hook entries in ~/.claude/settings.json — adds them when absent, removes them when present."
---

# Self-Reflect Toggle

Toggle the self-improvement signal capture system on or off.

## How It Works

The self-improvement system uses Claude Code hooks to silently capture learning signals during normal work. This skill adds or removes those hooks from `~/.claude/settings.json`.

When enabled, four hooks are active:
- **PreCompact** — Mines the transcript for corrections, conventions, and patterns before compaction
- **PostToolUseFailure** — Logs tool failures as learning signal candidates (async)
- **SessionEnd** — Extracts a lightweight session summary
- **SessionStart** (compact) — Re-injects captured signals after context compaction

## Process

### 1. Detect plugin install path

Determine the absolute path to the `hooks/` directory within this plugin. The hooks directory is at `self-reflect/hooks/` relative to this skill's parent directory. Resolve to an absolute path — this is needed for the hook commands in settings.json.

To find it: this SKILL.md is at `<plugin-root>/skills/self-reflect-toggle/SKILL.md`. The hooks are at `<plugin-root>/skills/self-reflect/hooks/`. Use Bash to resolve the absolute path:
```bash
PLUGIN_ROOT="$(cd "$(dirname "<path-to-this-SKILL.md>")/../../skills/self-reflect/hooks" && pwd)"
```

### 2. Read current settings

Read `~/.claude/settings.json`. If it doesn't exist, start with an empty object `{}`.

### 3. Detect current state

Check if any hook entries in `settings.json` have commands containing `self-reflect` in the path. If found, the system is currently **enabled**.

### 4. Toggle

#### If currently enabled → Disable

1. Remove all hook entries from `PreCompact`, `PostToolUseFailure`, `SessionEnd`, and `SessionStart` arrays where the command contains `self-reflect`
2. If removing an entry leaves an empty array, remove the entire key
3. Preserve all other hooks (e.g., Notification hooks)
4. Write updated `settings.json`
5. Report: "Self-improvement **disabled** — hooks removed. Changes take effect on next session or after `/hooks` review."

#### If currently disabled → Enable

1. Create `~/.claude/reflections/` directory if it doesn't exist
2. Add these hook entries to `settings.json`, merging with any existing hooks:

```json
{
  "hooks": {
    "PreCompact": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"<HOOKS_DIR>/capture-signals.py\"",
            "timeout": 30
          }
        ]
      }
    ],
    "PostToolUseFailure": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "bash \"<HOOKS_DIR>/capture-failure.sh\"",
            "async": true,
            "timeout": 5
          }
        ]
      }
    ],
    "SessionEnd": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"<HOOKS_DIR>/capture-session-summary.py\"",
            "timeout": 30
          }
        ]
      }
    ],
    "SessionStart": [
      {
        "matcher": "compact",
        "hooks": [
          {
            "type": "command",
            "command": "bash \"<HOOKS_DIR>/inject-signals.sh\""
          }
        ]
      }
    ]
  }
}
```

Replace `<HOOKS_DIR>` with the absolute path detected in step 1.

3. When merging, preserve existing hook entries under each event key. Append the new entries to existing arrays, do not replace them.
4. Write updated `settings.json`
5. Report: "Self-improvement **enabled** — 4 hooks added. Restart your session or run `/hooks` to review."

### 5. Verify hooks directory

After toggling, verify the hooks directory exists and contains the expected scripts:
- `capture-signals.py`
- `capture-failure.sh`
- `capture-session-summary.py`
- `inject-signals.sh`
- `memory_store.py`

If any are missing, warn: "Warning: hook script `<name>` not found at `<path>`. The hook may fail at runtime."

## Edge Cases

- **settings.json doesn't exist**: Create it with just the hooks object when enabling. Create `{}` as base.
- **settings.json has no hooks key**: Add the hooks key when enabling.
- **Other hooks exist**: Always preserve them. Only add/remove entries with `self-reflect` in the command path.
- **Partial state** (some hooks present, others missing): Treat as enabled. Disable removes all self-reflect hooks. Re-enable adds the full set.
- **hooks directory not found**: Report error and do not add hooks. Suggest reinstalling the plugin.
```

**Step 2: Verify the file renders correctly**

Read back the file and confirm markdown formatting is clean.

**Step 3: Commit**

```bash
git add plugins/self-improvement/skills/self-reflect-toggle/SKILL.md
git commit -m "feat(self-improvement): rewrite reflect-toggle for hook-based system"
```

---

### Task 9: /reflect SKILL.md — Enhanced reflection skill

Rewrite the core reflection skill with 7-step process, dual-scope proposals, FIFO ordering, and signal file integration.

**Files:**
- Modify: `plugins/self-improvement/skills/self-reflect/SKILL.md`

**Step 1: Write the new SKILL.md**

```markdown
---
name: self-reflect
description: "Use when the user invokes /reflect for a comprehensive review of learning moments. Reads hook-captured signals and the conversation, deduplicates, and proposes improvements one at a time (oldest first). Supports dual-scope: agent-side (CLAUDE.md) and project-side (.claude/improvements.md) proposals."
---

# Self-Reflect

Comprehensive review of learning moments from hook-captured signals and the current conversation. Proposes improvements one at a time, oldest first.

## Process

### 1. Gather

Collect learning candidates from two sources:

**Source A — Hook-captured signals:**
1. Check if `~/.claude/reflections/signals.jsonl` exists
2. If it does, read it (use `cat` and parse the JSONL) and filter to entries with `"status": "captured"`
3. These are signals captured by hooks during this and previous sessions

**Source B — Conversation scan:**
4. Scan the current conversation for learning moments across all categories:
   - **Commands**: build, test, deploy, lint, or workflow commands discovered or shared
   - **Conventions**: project patterns (naming, structure, imports, architecture)
   - **Gotchas**: subtle bugs, unexpected behavior, environment quirks, non-obvious fixes
   - **Preferences**: user workflow preferences, commit style, communication style
   - **Project friction**: navigation confusion, misleading file names, missing documentation

5. Merge Source A and Source B into a single candidate list

### 2. Deduplicate

For each candidate, check against these baselines and skip if already present:

1. **Existing CLAUDE.md files** — Read both:
   - Global: `~/.claude/CLAUDE.md`
   - Project: `CLAUDE.md` or `.claude/CLAUDE.md` in the project root
2. **Existing learnings** — Read `~/.claude/reflections/learnings/LEARNINGS.md` if it exists
3. **Existing improvements** — Read `.claude/improvements.md` in the project root if it exists
4. **Already-processed signals** — Skip signals with status `analyzed`, `promoted`, or `dismissed`
5. **Conversation context** — Skip if you already proposed this insight earlier in this session
6. **Semantic grouping** — Merge semantically similar candidates (e.g., "use pnpm not npm" and "don't use npm" become one candidate). Keep the most specific/complete version.

### 3. Classify

For each remaining candidate, determine:

- **Scope**: global (applies across all projects) vs project-specific
- **Type**: agent-side (teaches Claude how to work) vs project-side (suggests the project should change)
- **Category**:
  - Agent-side: `Commands`, `Conventions`, `Gotchas`, `Preferences`
  - Project-side: `Documentation`, `Naming`, `Project Structure`, `Configuration`, `Test Structure`
- **Confidence**: Boost signals that recur across multiple sessions:
  - 1 occurrence → low
  - 2 occurrences → medium
  - 3+ occurrences → high

Sort the final list by timestamp, oldest first (FIFO).

### 4. Present & Approve

**If 0 candidates**: Respond "Nothing to reflect on — no learning moments found."

**If all duplicates**: Respond "All learnings from this session are already captured."

**If 10+ candidates**, offer an escape hatch first:

```
Found 14 learning candidates. Process them one by one (oldest first)?
```

Use `AskUserQuestion`:
- "Yes, let's go" — process one by one
- "Show summary first" — list all as one-liners, then process individually
- "Skip all" — dismiss everything

**For each candidate** (one at a time, oldest first), display:

```
Learning 1 of 7 — correction (medium confidence)

  Use `pnpm test:unit` not `npm test` in this project

  Context: User said "No, use pnpm not npm" (session 2026-02-10)
  Source: hook-captured signal
```

Then `AskUserQuestion` with options:
- "Add to project CLAUDE.md" — project-scoped agent learning
- "Add to global CLAUDE.md" — cross-project agent learning
- "Add to improvements.md" — project-side improvement proposal
- "Skip" — dismiss this candidate

### 5. Write (immediately after each approval)

**For agent-side approvals** ("Add to project/global CLAUDE.md"):

1. Read the target CLAUDE.md file
2. Back up the file: copy to `<filename>.bak` before writing
3. Find the matching section header (e.g., `## Commands`, `## Gotchas`)
4. Append the entry under that section
5. If the section doesn't exist, create it at the end of the file
6. If the file doesn't exist, create it with this template:

```markdown
# [Project Name or Global]

## Commands

## Conventions

## Gotchas

## Preferences
```

For project-level files, create at `.claude/CLAUDE.md` relative to the project root.

7. Also update `~/.claude/reflections/learnings/LEARNINGS.md`:
   - Create the file and directory if they don't exist
   - Find or create the matching category section
   - Append: `- [LRN-YYYYMMDD-NNN] <content> (promoted to <target>)`

**For project-side approvals** ("Add to improvements.md"):

1. Read `.claude/improvements.md` in the project root
2. If it doesn't exist, create it with this template:

```markdown
# Project Improvements

Proposed by `/reflect` — review and apply at your pace.

## Pending

## Applied

## Deferred
```

3. Append under `## Pending`:

```markdown
### [YYYY-MM-DD] <title>
- **Category**: <category>
- **Impact**: <Low/Medium/High>
- **Details**: <description>
- **Suggested action**: <concrete action>
- **Confidence**: <Low/Medium/High> (<reasoning>)
```

4. Also update `LEARNINGS.md` with the promotion record.

**For skipped items**: Mark as dismissed (step 6).

### 6. Update signal status

After each item is processed (approved or skipped):

1. If the candidate came from `signals.jsonl` (has a signal ID):
   - If approved: update the signal's status to `promoted` and set `promoted_to` to the target file path
   - If skipped: update the signal's status to `dismissed`
2. These updates should be done by reading, modifying, and rewriting the relevant line in `signals.jsonl`

This ensures the user can stop at any point — processed items are persisted, remaining items stay as `captured` for the next `/reflect` run.

### 7. Clean up

After all candidates are processed (or the user stops):

1. Prune signals older than 14 days from `signals.jsonl`:
   - Read the file, filter out entries where timestamp is >14 days old AND status is `captured` or `dismissed`
   - Never prune `promoted` entries (they have historical value in the learnings index)
   - Rewrite the file
2. Report summary: "Reflected on N items: X added, Y skipped."

## Edge Cases

- **signals.jsonl doesn't exist**: Skip signal processing, rely on conversation scan only
- **signals.jsonl is empty**: Same as above
- **No project open** (running from `~` or similar): Skip project-scoped proposals. Only propose global additions. Do not offer "Add to project CLAUDE.md" or "Add to improvements.md" options.
- **LEARNINGS.md doesn't exist**: Create it when first promoting an entry
- **improvements.md doesn't exist**: Create it when first adding a project-side proposal
- **Multiple projects touched in one session**: Group candidates by project context. Present project-scoped items with the project path visible.
- **User stops mid-way**: Processed items are already persisted. Remaining signals stay as `captured`.

## Status Line (optional)

See [docs/statusline-setup.md](../docs/statusline-setup.md) to display pending learning counts in your Claude Code status bar.
```

**Step 2: Verify formatting**

Read back and confirm the markdown is clean and all sections are present.

**Step 3: Commit**

```bash
git add plugins/self-improvement/skills/self-reflect/SKILL.md
git commit -m "feat(self-improvement): rewrite reflect skill for v3 dual-scope system"
```

---

### Task 10: statusline-setup.md — Documentation guide

**Files:**
- Create: `plugins/self-improvement/docs/statusline-setup.md`

**Step 1: Write the guide**

```markdown
# Status Line: Pending Learnings Count

Show the number of pending learning signals in your Claude Code status bar so you know when to run `/reflect`.

## What it shows

When signals have been captured by hooks but not yet reviewed:
```
reflect: 5 pending
```

When no signals are pending, the status line shows nothing (empty string).

## Setup

### 1. Locate memory_store.py

Find the absolute path to `memory_store.py` in your plugin installation. It's in the `self-reflect/hooks/` directory. For example:

```
~/.claude/plugins/cache/<plugin-path>/skills/self-reflect/hooks/memory_store.py
```

You can find it by running:
```bash
find ~/.claude -name "memory_store.py" -path "*/self-reflect/*" 2>/dev/null
```

### 2. Add to settings.json

Open `~/.claude/settings.json` and add or update the `statusLine` key:

```json
{
  "statusLine": {
    "type": "command",
    "command": "python3 \"/absolute/path/to/hooks/memory_store.py\" stats --format statusline"
  }
}
```

Replace `/absolute/path/to/hooks/memory_store.py` with the actual path from step 1.

### 3. Combine with existing status line

If you already have a status line command, you can combine them in a wrapper script. Create `~/.claude/statusline-wrapper.sh`:

```bash
#!/usr/bin/env bash

# Your existing status line output
EXISTING=$(<your-existing-command> 2>/dev/null || echo "")

# Pending learnings count
MEMORY_STORE="/absolute/path/to/hooks/memory_store.py"
REFLECT=$(python3 "$MEMORY_STORE" stats --format statusline 2>/dev/null || echo "")

# Combine (pipe-separated)
PARTS=()
[ -n "$EXISTING" ] && PARTS+=("$EXISTING")
[ -n "$REFLECT" ] && PARTS+=("$REFLECT")

IFS='|' ; echo "${PARTS[*]}"
```

Then set your statusLine to:
```json
{
  "statusLine": {
    "type": "command",
    "command": "bash ~/.claude/statusline-wrapper.sh"
  }
}
```

## Customization

The `memory_store.py stats --format statusline` command outputs:
- `reflect: N pending` when there are `N` signals with status `captured` or `analyzed`
- Empty string when there are no pending signals

To customize the format, you can wrap the command:
```bash
COUNT=$(python3 /path/to/memory_store.py stats --format statusline 2>/dev/null)
[ -n "$COUNT" ] && echo "🔍 $COUNT"
```
```

**Step 2: Commit**

```bash
git add plugins/self-improvement/docs/statusline-setup.md
git commit -m "docs(self-improvement): add status line setup guide"
```

---

### Task 11: Update plugin.json

**Files:**
- Modify: `plugins/self-improvement/.claude-plugin/plugin.json`

**Step 1: Update the plugin metadata**

```json
{
  "name": "self-improvement",
  "description": "Memory-driven self-improvement system. Hooks capture learning signals silently during work. /reflect reviews signals and proposes dual-scope improvements (CLAUDE.md entries + project improvement proposals). /reflect-toggle enables or disables the hook-based capture system.",
  "version": "0.2.0",
  "author": {
    "name": "Julian Wulff"
  },
  "repository": "https://github.com/jsonwulff/skills",
  "license": "MIT",
  "keywords": ["self-improvement", "reflection", "learning", "claude-md", "hooks", "memory", "signals"],
  "skills": [
    "./skills/self-reflect",
    "./skills/self-reflect-toggle"
  ]
}
```

**Step 2: Commit**

```bash
git add plugins/self-improvement/.claude-plugin/plugin.json
git commit -m "chore(self-improvement): update plugin.json for v3"
```

---

### Task 12: End-to-end verification

Manual verification that all components work together.

**Step 1: Verify file structure**

```bash
find plugins/self-improvement -type f | sort
```

Expected:
```
plugins/self-improvement/.claude-plugin/plugin.json
plugins/self-improvement/docs/statusline-setup.md
plugins/self-improvement/skills/self-reflect-toggle/SKILL.md
plugins/self-improvement/skills/self-reflect/SKILL.md
plugins/self-improvement/skills/self-reflect/hooks/capture-failure.sh
plugins/self-improvement/skills/self-reflect/hooks/capture-session-summary.py
plugins/self-improvement/skills/self-reflect/hooks/capture-signals.py
plugins/self-improvement/skills/self-reflect/hooks/inject-signals.sh
plugins/self-improvement/skills/self-reflect/hooks/memory_store.py
plugins/self-improvement/skills/self-reflect/hooks/test_capture_signals.py
plugins/self-improvement/skills/self-reflect/hooks/test_memory_store.py
```

**Step 2: Run all tests**

```bash
cd plugins/self-improvement/skills/self-reflect/hooks && python3 -m pytest -v
```

Expected: All tests pass.

**Step 3: Verify capture-failure.sh end-to-end**

```bash
echo '{"tool_name":"Bash","error":"command not found: npm","session_id":"e2e-test"}' | \
  REFLECTIONS_DIR=/tmp/e2e-test \
  bash plugins/self-improvement/skills/self-reflect/hooks/capture-failure.sh

cat /tmp/e2e-test/signals.jsonl | python3 -m json.tool
```

Expected: Valid JSONL entry with type "failure".

**Step 4: Verify inject-signals.sh end-to-end**

```bash
echo '{"session_id":"e2e-test","source":"compact"}' | \
  REFLECTIONS_DIR=/tmp/e2e-test \
  bash plugins/self-improvement/skills/self-reflect/hooks/inject-signals.sh
```

Expected: JSON with `additionalContext` containing the failure signal from step 3.

**Step 5: Verify statusline output**

```bash
REFLECTIONS_DIR=/tmp/e2e-test python3 plugins/self-improvement/skills/self-reflect/hooks/memory_store.py stats --format statusline
```

Expected: `reflect: 1 pending`

**Step 6: Clean up**

```bash
rm -rf /tmp/e2e-test
```

**Step 7: Final commit (if any fixes were needed)**

```bash
git add -A plugins/self-improvement/
git commit -m "fix(self-improvement): address issues found in e2e verification"
```
