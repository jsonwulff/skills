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
            if entry.get("tool_use") or len(entry.get("content", "")) > 20:
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
