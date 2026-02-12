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

    base_dir = os.environ.get("REFLECTIONS_DIR")
    store = MemoryStore(base_dir=base_dir) if base_dir else MemoryStore()
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
