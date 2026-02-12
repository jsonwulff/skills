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
            **entry,
            "id": self._next_id(),
            "version": 1,
            "timestamp": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
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
