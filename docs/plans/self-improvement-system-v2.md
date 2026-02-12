# Redesign: Hook-Driven Self-Improvement System

## Context

The current self-improvement system embeds 38 lines of passive detection instructions into `~/.claude/CLAUDE.md`, which are loaded into every session. In practice this approach: consumes significant context, interrupts workflow with AskUserQuestion proposals during work, produces low-quality proposals, and often doesn't trigger at all because Claude forgets the instructions mid-task.

This redesign replaces the CLAUDE.md-based passive detection with a hook-driven approach that has **zero context overhead** during normal work, captures learning signals automatically at lifecycle boundaries, and keeps `/reflect` as the primary intelligent analysis mechanism.

## User Workflow

### Setup (one-time)
1. Run `/reflect-toggle` → hooks are added to settings.json, old CLAUDE.md section removed
2. Review hooks via `/hooks` menu or restart session

### During normal work (invisible to you)
- **You work normally** — zero impact on your workflow, no context consumed, no interruptions
- _System: When a tool fails, the PostToolUseFailure hook silently logs it to `~/.claude/reflections/signals.jsonl`_
- _System: When context compacts, the PreCompact hook silently extracts learning signals from the transcript before they're lost_
- _System: After compaction, the SessionStart hook injects a brief signal summary so /reflect can still see them_

### When you want to capture learnings
1. Run `/reflect` at any natural pause or session end
2. Claude scans the conversation + any hook-captured signals
3. You see grouped proposals: "Add X to project CLAUDE.md" / "Add Y to global CLAUDE.md"
4. Approve in batch or pick individually
5. Done — entries written, signals file cleaned up

### Toggling on/off
- `/reflect-toggle` → adds or removes hooks from settings.json
- No CLAUDE.md bloat either way

## Architecture Overview

```
 During Session                    At Compaction Boundary
┌──────────────────────┐          ┌─────────────────────────────┐
│  PostToolUseFailure  │          │  PreCompact hook            │
│  hook (async)        │──────┐   │  reads transcript,          │
│  logs tool failures  │      │   │  extracts correction/       │
└──────────────────────┘      │   │  discovery signals          │
                              ▼   └──────────┬──────────────────┘
                   ~/.claude/reflections/     │
                   signals.jsonl    ◄─────────┘
                              ▲
                              │   ┌─────────────────────────────┐
                              │   │  SessionStart hook          │
                              │   │  (matcher: "compact")       │
                              │   │  reads signals file,        │
                              │   │  injects additionalContext  │
                              │   │  so insights survive        │
                              │   │  compaction                 │
                              │   └─────────────────────────────┘
                              │
                              │   ┌─────────────────────────────┐
                              └───│  /reflect skill             │
                                  │  reads signals + conversation│
                                  │  deduplicates, classifies,  │
                                  │  proposes batch additions   │
                                  └─────────────────────────────┘
```

**Components:**

1. **PreCompact command hook** — Reads transcript before compaction, extracts candidate learning signals (corrections, repeated failures, conventions), writes them to `~/.claude/reflections/signals.jsonl`
2. **SessionStart command hook** (matcher: `"compact"`) — After compaction, reads signals file and injects a compact summary as `additionalContext` so insights survive in the post-compaction context
3. **PostToolUseFailure command hook** (async) — Logs tool failures to the signals file as gotcha candidates
4. **Enhanced `/reflect` skill** — Reads conversation + signals file for comprehensive review
5. **Reworked `/reflect-toggle` skill** — Toggles hooks in `~/.claude/settings.json` instead of toggling CLAUDE.md content
6. **No CLAUDE.md passive section** — Zero context overhead

## Component Details

### 1. PreCompact Hook Script (`capture-signals.py`)

**Trigger**: Before context compaction (manual or auto)
**Type**: command (synchronous — runs before compaction proceeds)
**Timeout**: 30 seconds

The script reads the transcript JSONL file and extracts candidate learning signals using pattern matching. The intelligence stays in `/reflect` — this script just captures raw candidates.

**Signal detection heuristics:**
- **Corrections**: User messages containing patterns like "no,", "wrong", "actually", "instead", "that's not", "should be", "use X instead" appearing after a Claude response
- **Repeated failures**: Same tool failing 2+ times consecutively
- **Multi-attempt edits**: Same file edited 3+ times in sequence
- **Convention signals**: User messages with "always use", "we prefer", "our convention", "naming"
- **Command sharing**: User messages with backtick-wrapped commands or "run" instructions

**Output format** (`~/.claude/reflections/signals.jsonl`):
```jsonl
{"ts":"2026-02-11T10:23:00Z","sid":"abc123","type":"correction","context":"User said: 'No, use pnpm not npm in this project'","turn":42}
{"ts":"2026-02-11T10:25:00Z","sid":"abc123","type":"failure","context":"Bash: npm test failed (exit 1)","turn":45}
```

**Key design decision**: Pattern matching produces false positives — that's fine. `/reflect` filters them with LLM intelligence. False negatives (missed signals) are also acceptable because `/reflect` independently scans the conversation.

### 2. SessionStart Hook Script (`inject-signals.sh`)

**Trigger**: After compaction completes (matcher: `"compact"`)
**Type**: command (synchronous)

Reads `~/.claude/reflections/signals.jsonl`, filters to the current session, and returns a compact summary via `additionalContext`. This ensures that signals captured before compaction remain visible to Claude (and to `/reflect`) in the post-compaction context.

**Output** (JSON to stdout):
```json
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "Self-improvement signals captured before compaction:\n- [correction] 'Use pnpm not npm' (turn 42)\n- [failure] npm test failed (turn 45)\nRun /reflect to review and persist these learnings."
  }
}
```

If no signals exist for the current session, the script exits 0 with no output (no context injected).

### 3. PostToolUseFailure Hook Script (`capture-failure.sh`)

**Trigger**: After any tool failure
**Type**: command, async (non-blocking)
**Timeout**: 5 seconds

Lightweight script that appends the failure to the signals file. Tool failures are high-value signals for the "Gotchas" category.

**Appends**:
```jsonl
{"ts":"...","sid":"...","type":"failure","context":"Bash: <command> failed: <error excerpt>","tool":"Bash","turn":0}
```

### 4. Enhanced `/reflect` Skill

**Changes from current implementation:**

In **Step 1 (Gather)**, add:
- Read `~/.claude/reflections/signals.jsonl` for hook-captured signals
- These supplement the conversation scan — signals from the file may reference context lost to compaction
- Use the `context` field from each signal as a starting point for analysis

In **Step 2 (Deduplicate)**, add:
- Deduplicate against signals already processed in previous `/reflect` runs (check the signals file for a `processed` flag)

After **Step 6 (Write)**, add new step:
- **Step 7: Cleanup** — Mark processed signals in the signals file (or remove them). Clear signals older than 7 days.

New **Edge Case**:
- Signals file doesn't exist or is empty → skip signals processing, rely on conversation scan only (graceful degradation)

### 5. Reworked `/reflect-toggle` Skill

**What it toggles**: Hooks in `~/.claude/settings.json` (not CLAUDE.md content)

**Enable flow:**
1. Read `~/.claude/settings.json`
2. Add PreCompact, SessionStart (compact), and PostToolUseFailure hook entries to the `hooks` object
3. Preserve all existing hooks (e.g., the Notification hook)
4. Write updated settings.json
5. Report: "Self-improvement **enabled** — hooks will capture learning signals automatically."

**Disable flow:**
1. Read `~/.claude/settings.json`
2. Remove the three self-improvement hook entries (identified by script paths containing `self-reflect`)
3. Preserve all other hooks
4. Write updated settings.json
5. Report: "Self-improvement **disabled** — hooks removed."

**Migration**: If `~/.claude/CLAUDE.md` contains the old `## Self-Improvement` section, remove it during enable/disable (one-time migration from old system).

**Important**: Settings changes require `/hooks` review or session restart to take effect. The skill should inform the user of this.

### 6. CLAUDE.md Changes

**Remove entirely**: The 38-line `## Self-Improvement` section from `~/.claude/CLAUDE.md`. The file may become empty, which is fine — it will accumulate content as `/reflect` writes learned insights.

## Settings.json Hook Configuration (When Enabled)

```json
{
  "hooks": {
    "Notification": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "terminal-notifier -title 'Claude Code' -message 'Needs your attention' -sound default -activate com.apple.Terminal"
          }
        ]
      }
    ],
    "PreCompact": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"$HOME/.claude/skills/self-reflect/hooks/capture-signals.py\"",
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
            "command": "bash \"$HOME/.claude/skills/self-reflect/hooks/inject-signals.sh\""
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
            "command": "bash \"$HOME/.claude/skills/self-reflect/hooks/capture-failure.sh\"",
            "async": true,
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

## File Structure

```
~/Development/skills/skills/
  self-reflect/
    SKILL.md                     # Enhanced: adds signals file awareness + cleanup step
    hooks/                       # NEW directory
      capture-signals.py         # PreCompact: transcript parser (Python)
      inject-signals.sh          # SessionStart(compact): context injector (Bash)
      capture-failure.sh         # PostToolUseFailure: failure logger (Bash)
  self-reflect-toggle/
    SKILL.md                     # Rewritten: toggles hooks in settings.json
```

Scripts are accessible via the existing symlink: `~/.claude/skills/self-reflect` → `~/Development/skills/skills/self-reflect`

Runtime data:
```
~/.claude/reflections/
  signals.jsonl                  # Accumulated learning signals (created by hooks)
```

## Files to Modify

| File | Action | Description |
|------|--------|-------------|
| `skills/self-reflect/SKILL.md` | Edit | Add signals file reading in Gather, dedup in Deduplicate, cleanup in new Step 7 |
| `skills/self-reflect-toggle/SKILL.md` | Rewrite | Switch from CLAUDE.md toggling to settings.json hook toggling |
| `skills/self-reflect/hooks/capture-signals.py` | Create | PreCompact transcript parser |
| `skills/self-reflect/hooks/inject-signals.sh` | Create | SessionStart context injector |
| `skills/self-reflect/hooks/capture-failure.sh` | Create | PostToolUseFailure logger |
| `~/.claude/CLAUDE.md` | Edit | Remove the `## Self-Improvement` section |

All paths are relative to `~/Development/skills/` unless prefixed with `~/`.

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Hooks in settings.json, not skill frontmatter** | Skill frontmatter hooks are scoped to the skill's lifetime only; we need always-on hooks |
| **PreCompact = command hook, not agent** | PreCompact doesn't support additionalContext; agent hooks add cost for no benefit here |
| **SessionStart(compact) for context injection** | Only hook event post-compaction that supports additionalContext |
| **Python for transcript parsing** | JSONL parsing + regex pattern matching is significantly more robust in Python than bash+jq |
| **Async PostToolUseFailure** | Tool failures are frequent; async prevents blocking Claude's response |
| **Pattern matching, not LLM analysis in hooks** | Hooks should be cheap and fast; intelligent analysis belongs in /reflect |
| **Zero CLAUDE.md overhead** | The entire motivation — hooks replace the 38-line passive detection section |
| **signals.jsonl, not a directory of files** | Simple append-only log; easy to read, filter, and clean up |

## Edge Cases

- **No Python installed**: `capture-signals.py` should check `python3` availability; degrade gracefully (exit 0)
- **No jq installed**: Bash scripts should check for jq; degrade gracefully
- **Signals file grows unbounded**: `/reflect` cleanup step + signals older than 7 days auto-pruned by `capture-signals.py`
- **Concurrent sessions**: Use `session_id` to partition signals; `/reflect` reads only current session
- **Transcript too large**: Cap processing to last 200 turns (older content was captured by previous compaction cycles)
- **Hook timeout**: 30s for PreCompact, 5s for failures — silent degradation on timeout
- **Settings.json race**: Warn user that hook changes require `/hooks` review or session restart

## Verification

1. **Enable hooks**: Run `/reflect-toggle` → verify hooks appear in `~/.claude/settings.json`, old CLAUDE.md section removed
2. **Tool failure capture**: Cause a deliberate tool failure → verify entry in `~/.claude/reflections/signals.jsonl`
3. **PreCompact capture**: In a long session, trigger `/compact` → verify signals extracted from transcript
4. **Post-compaction injection**: After compaction, verify SessionStart hook injected additionalContext with signal summary
5. **`/reflect` with signals**: Run `/reflect` → verify it reads signals file alongside conversation, proposes entries, writes approved ones
6. **Cleanup**: After `/reflect` approves entries → verify signals file is cleaned up
7. **Disable hooks**: Run `/reflect-toggle` → verify hooks removed from settings.json, other hooks preserved
8. **Graceful degradation**: Delete signals file → run `/reflect` → verify it works with conversation-only scan
