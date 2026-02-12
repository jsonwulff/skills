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
        from datetime import timedelta
        cutoff_dt = datetime.now(timezone.utc) - timedelta(days=days)
        cutoff_ts = cutoff_dt.isoformat(timespec="seconds").replace("+00:00", "Z")

        keep = []
        removed = 0
        for e in entries:
            ts = e.get("timestamp", "")
            entry_status = e.get("status", "")
            # Never prune confirmed/promoted entries
            if entry_status in ("promoted", "confirmed"):
                keep.append(e)
                continue
            if status_filter and entry_status != status_filter:
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
