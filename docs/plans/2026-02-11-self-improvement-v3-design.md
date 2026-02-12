# Self-Improvement System v3: Design Document

## Overview

A memory-backed reflection system for Claude Code that captures learning signals automatically via hooks, stores them in structured file formats, and surfaces them through an enhanced `/reflect` skill that proposes dual-scope improvements (agent-side CLAUDE.md entries and project-side improvement proposals). Zero context overhead during normal work. All improvements proposed, never auto-applied.

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| SessionEnd hook | Include in v3.0 | Catches short sessions that never trigger compaction |
| Storage layers | 3-layer (signals → learnings → CLAUDE.md) | Can remove intermediate layer later if it doesn't add value |
| Project-side proposals | Yes, via `.claude/improvements.md` | Key v3 differentiator: dual-scope improvements |
| Hook languages | Python for transcript parsing, Bash for simple ops | JSONL + regex more robust in Python; Bash sufficient for append/inject |
| Storage abstraction | `memory_store.py` shared module | Clean interface boundary, enables future SQLite swap |
| Hook path resolution | Detect plugin install path at runtime | `/reflect-toggle` resolves paths when writing hooks to settings.json |
| v1 migration | None | Not yet published; no users to migrate |
| Dependency errors | User-facing messages | Hooks output warnings about missing Python 3 or jq via additionalContext/stderr |
| Status line | Documentation guide, not built-in | `docs/statusline-setup.md` explains optional setup |

## Architecture

```
                     CAPTURE LAYER (hooks, silent, zero context)
                     ============================================
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│  PreCompact       │  │ PostToolUse      │  │ SessionEnd       │
│  capture-signals  │  │ Failure          │  │ capture-session  │
│  .py              │  │ capture-failure  │  │ -summary.py      │
│                   │  │ .sh (async)      │  │                  │
│  Transcript mining│  │ Logs tool name,  │  │ Extracts session │
│  - corrections    │  │ error excerpt    │  │ summary: what    │
│  - conventions    │  │                  │  │ accomplished,    │
│  - repeated fails │  │                  │  │ key decisions,   │
│  - discoveries    │  │                  │  │ unresolved issues│
│  - friction       │  │                  │  │                  │
└────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘
         │                     │                      │
         ▼                     ▼                      ▼
┌────────────────────────────────────────────────────────────────┐
│              ~/.claude/reflections/signals.jsonl                │
│              Ephemeral raw captures (14-day TTL)               │
│              Accessed via memory_store.py                       │
└───────────────────────────┬────────────────────────────────────┘
                            │
     CONTEXT INJECTION      │
     (post-compaction)      │
┌───────────────────────────┴────────────────────────────────────┐
│  SessionStart hook (matcher: "compact")                        │
│  inject-signals.sh                                             │
│  Reads signals for current session, injects additionalContext  │
└────────────────────────────────────────────────────────────────┘
                            │
     ANALYSIS LAYER         │
     (/reflect, user-initiated)
┌───────────────────────────┴────────────────────────────────────┐
│                        /reflect                                 │
│                                                                 │
│  1. GATHER     Read signals.jsonl + conversation + baselines   │
│  2. DEDUPLICATE Against CLAUDE.md, learnings, improvements.md  │
│  3. CLASSIFY   Scope (global/project), type (agent/project),  │
│                category, confidence boost for recurrence        │
│  4. PRESENT    One candidate at a time, oldest first (FIFO)    │
│  5. APPROVE    Per-item: add to CLAUDE.md / improvements.md /  │
│                skip. Escape hatch for 10+ candidates.           │
│  6. WRITE      Approved → target file (back up first) +       │
│                learnings index. Immediate per-item persistence. │
│  7. CLEAN UP   Mark signals, prune >14 days, update index     │
└────────────────────────────────────────────────────────────────┘
                            │
     STORAGE LAYER          │
     (permanent)            │
┌───────────────────────────┴────────────────────────────────────┐
│                                                                 │
│  ~/.claude/reflections/learnings/                               │
│    LEARNINGS.md              Analyzed/promoted entry index      │
│    <topic>.md                Overflow detail files              │
│                                                                 │
│  Promotion targets:                                             │
│    ~/.claude/CLAUDE.md              Global agent preferences    │
│    <project>/CLAUDE.md              Project conventions         │
│    <project>/.claude/CLAUDE.md      Project conventions         │
│    <project>/.claude/improvements.md  Project improvement props │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
                            │
     TOGGLE LAYER           │
┌───────────────────────────┴────────────────────────────────────┐
│  /reflect-toggle                                                │
│                                                                 │
│  ON:  Detects plugin install path. Adds PreCompact,            │
│       PostToolUseFailure, SessionEnd, SessionStart(compact)    │
│       hooks to ~/.claude/settings.json. Creates reflections/.  │
│  OFF: Removes hooks with self-reflect in path. Preserves rest. │
└────────────────────────────────────────────────────────────────┘
```

## Signal Entry Schema

Each line in `signals.jsonl`:

```json
{
  "id": "SIG-20260211-0001",
  "version": 1,
  "timestamp": "2026-02-11T10:23:00Z",
  "session_id": "abc123",
  "type": "correction",
  "status": "captured",
  "confidence": 2,
  "source": {
    "hook": "PreCompact",
    "turn": 42,
    "file": "/path/to/relevant/file"
  },
  "content": "Use pnpm, not npm, in this project",
  "context": "User said: 'No, use pnpm not npm'",
  "category": "command",
  "tags": ["package-manager"],
  "related": [],
  "promoted_to": null,
  "meta": {}
}
```

### Field definitions

- **type**: `correction | failure | convention | command | gotcha | discovery | pattern | project_friction | summary`
- **status**: `captured → analyzed → promoted | dismissed | archived`
- **confidence**: `1` low (single), `2` medium (2 occurrences), `3` high (3+), `4` verified (user-confirmed)
- **category**: `command | convention | gotcha | preference | project-structure | documentation | naming | test-structure | configuration`
- **version**: Enables schema evolution without breaking old entries
- **source.hook**: Which hook captured this signal
- **source.turn**: Approximate turn number in the transcript
- **source.file**: Relevant file path if applicable
- **related**: IDs of semantically related signals (populated by `/reflect`)
- **promoted_to**: Target file path when status is `promoted`
- **meta**: Escape hatch for future fields

## Capture Heuristics

### PreCompact — `capture-signals.py`

| Pattern | Detection Keywords | Signal Type | Confidence |
|---------|-------------------|-------------|------------|
| User correction | "no,", "nope", "wrong", "incorrect", "that's not right", "not quite", "actually", "instead", "rather", "should be", "supposed to be", "meant to", "I meant", "use X not Y", "don't use", "stop using", "switch to", "prefer X over", "we don't do that", "that's outdated", "that changed", "not anymore", "deprecated" | `correction` | 2 |
| Convention statement | "always use", "never use", "we prefer", "our convention", "our standard", "the convention is", "the pattern is", "in this project", "in this repo", "in this codebase", "around here", "on this team", "naming convention", "file structure", "folder structure", "we put X in Y", "X goes in Y", "we keep X in", "we follow", "we stick to", "house rule", "code style", "our approach" | `convention` | 2 |
| Positive reinforcement | "perfect", "exactly", "exactly right", "that's it", "nailed it", "spot on", "love it", "great", "nice", "looks good", "that works", "that's correct", "yes that's right", "good approach", "awesome", "brilliant", "excellent", "well done", "much better" (only after multi-step Claude action) | `pattern` | 1 |
| Repeated failure | Same tool failing 2+ times consecutively | `failure` | 2 |
| Multi-attempt edit | Same file edited 3+ times in sequence | `pattern` | 1 |
| Command sharing | Backtick-wrapped commands, "run \`X\`" | `command` | 2 |
| Search thrashing | 3+ Glob/Grep with empty results before finding target | `project_friction` | 1 |
| Missing context | Claude asks a question CLAUDE.md could have answered | `discovery` | 2 |
| Workflow correction | "use X instead of Y" where X/Y are tools/commands | `correction` | 3 |

Philosophy: over-capture at hook time, smart filtering at `/reflect` time. False positives cost bytes; false negatives cost repeated mistakes across sessions.

### PostToolUseFailure — `capture-failure.sh`

Calls `memory_store.py append` with type `failure`, confidence `1`, tool name + error excerpt. Async, 5s timeout.

### SessionEnd — `capture-session-summary.py`

Reads transcript, extracts: files touched, tools used, turn count, brief text summary. Writes single `summary` type entry. 30s timeout.

### SessionStart — `inject-signals.sh`

Matcher: `"compact"`. Reads `memory_store.py query --session current`, formats compact summary, outputs JSON with `additionalContext`. Exits 0 with no output if no signals exist.

## memory_store.py Interface

```python
append(entry)                          # Write signal to signals.jsonl
query(status, type, since, tags, sid)  # Filter signals
get(id)                                # Single entry by ID
update(id, fields)                     # Update status, confidence, etc.
archive(before_date, status_filter)    # Bulk prune/archive
stats()                                # Counts by status, type, category
promote(id, target, content)           # Move to learnings + record target
```

Also callable as CLI: `python3 memory_store.py append '{"type":"failure",...}'`, `python3 memory_store.py stats --format statusline`.

## /reflect Skill Process

### Step 1: Gather
- Read `signals.jsonl` via `memory_store.py query --status captured`
- Scan current conversation for learning moments
- Read existing CLAUDE.md files (global + project) for dedup baseline
- Read `LEARNINGS.md` for dedup baseline
- Read `.claude/improvements.md` if it exists

### Step 2: Deduplicate
- Against existing CLAUDE.md entries
- Against existing learnings
- Against existing improvements.md proposals
- Against signals already marked `analyzed`/`promoted`/`dismissed`
- Semantic grouping: merge "use pnpm not npm" and "don't use npm" into one candidate

### Step 3: Classify
- **Scope**: global (cross-project) vs project-specific
- **Type**: agent-side (CLAUDE.md) vs project-side (improvement proposal)
- **Category**: commands, conventions, gotchas, preferences, project-structure, documentation, naming, configuration, test-structure
- **Confidence**: boost signals recurring across sessions (2+ → medium, 3+ → high)

### Step 4: Present
One candidate at a time, oldest first (FIFO):

```
Learning 1 of 7 — correction (from 2 sessions ago)

  Use `pnpm test:unit` not `npm test` in this project

  Context: User said "No, use pnpm not npm" (session 2026-02-10)
  Confidence: medium (2 occurrences)
```

If 10+ candidates, offer escape hatch upfront:
- "Yes, let's go" — process one by one
- "Show me a summary first" — list all as one-liners, then process individually
- "Skip all" — dismiss everything

### Step 5: Approve
`AskUserQuestion` per item:
- "Add to project CLAUDE.md"
- "Add to global CLAUDE.md"
- "Add to improvements.md" (for project-side proposals)
- "Skip"

Each item is written/dismissed immediately. User can stop at any point — processed items are persisted, remaining stay as `captured`.

### Step 6: Write
- Agent-side approved → target CLAUDE.md (back up first)
- Also write to `LEARNINGS.md` with status `promoted` and `promoted_to` field
- Project-side approved → append to `.claude/improvements.md` under Pending

### Step 7: Clean up
- Mark processed signals as `analyzed`, `promoted`, or `dismissed`
- Prune signals older than 14 days
- Update `LEARNINGS.md` index

## /reflect-toggle Skill Process

### Enable
1. Read `~/.claude/settings.json`
2. Detect plugin install path (resolve from own SKILL.md location)
3. Add four hook entries, preserving existing hooks:
   - `PreCompact` → `capture-signals.py` (sync, 30s)
   - `PostToolUseFailure` → `capture-failure.sh` (async, 5s)
   - `SessionEnd` → `capture-session-summary.py` (sync, 30s)
   - `SessionStart` (matcher: `"compact"`) → `inject-signals.sh` (sync)
4. Create `~/.claude/reflections/` directory if needed
5. Report: "Self-improvement **enabled** — 4 hooks added. Restart your session or run `/hooks` to review."

### Disable
1. Read `~/.claude/settings.json`
2. Remove hook entries with `self-reflect` in command path
3. Preserve all other hooks
4. Report: "Self-improvement **disabled** — hooks removed."

## Settings.json Hook Configuration (When Enabled)

```json
{
  "hooks": {
    "PreCompact": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"/absolute/path/to/hooks/capture-signals.py\"",
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
            "command": "bash \"/absolute/path/to/hooks/capture-failure.sh\"",
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
            "command": "python3 \"/absolute/path/to/hooks/capture-session-summary.py\"",
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
            "command": "bash \"/absolute/path/to/hooks/inject-signals.sh\""
          }
        ]
      }
    ]
  }
}
```

Paths are resolved at enable time by `/reflect-toggle`.

## File Structure

```
plugins/self-improvement/
  .claude-plugin/plugin.json            # Updated: description, version bump
  docs/
    statusline-setup.md                 # Guide: pending learnings in status bar
  skills/
    self-reflect/
      SKILL.md                          # 7-step process, dual-scope, FIFO
      hooks/
        capture-signals.py              # PreCompact: transcript mining (Python)
        capture-session-summary.py      # SessionEnd: session summary (Python)
        capture-failure.sh              # PostToolUseFailure: failure logger (Bash)
        inject-signals.sh              # SessionStart(compact): context injector (Bash)
        memory_store.py                # Shared storage abstraction (Python)
    self-reflect-toggle/
      SKILL.md                          # Toggle hooks in settings.json

Runtime data:
~/.claude/reflections/
  signals.jsonl                         # Ephemeral raw captures (14-day TTL)
  learnings/
    LEARNINGS.md                        # Index of analyzed/promoted entries
    <topic>.md                          # Overflow detail files

Project-level:
<project>/.claude/improvements.md       # Project improvement proposals
```

## Learnings Format

### LEARNINGS.md (index)

```markdown
# Learnings

## Commands
- [LRN-20260211-001] Use `pnpm test:unit` not `npm test` (confirmed, 3 sessions)

## Conventions
- [LRN-20260211-002] API handlers go in `src/handlers/<resource>.handler.ts` (confirmed)

## Gotchas
- [LRN-20260212-001] `npm ci` silently succeeds with mismatched lockfile on Node 18 (confirmed)
```

### improvements.md (project-side)

```markdown
# Project Improvements

Proposed by `/reflect` — review and apply at your pace.

## Pending

### [2026-02-11] Document build commands
- **Category**: Documentation
- **Impact**: High
- **Details**: No README section documents how to build, test, or run the project.
- **Suggested action**: Add a `## Development` section to README.md.
- **Confidence**: High (build command discovery failed in 2 sessions)

## Applied

## Deferred
```

## Edge Cases

- **No Python 3**: Hooks output warning via `additionalContext`: "Self-improvement hooks require Python 3 but it wasn't found. Signal capture is disabled for this session." Exit 0.
- **No jq**: Bash hooks output warning: "Self-improvement hooks require jq but it wasn't found. Run `brew install jq` (macOS) or `apt install jq` (Linux)." Exit 0.
- **signals.jsonl missing**: Created on first write. `/reflect` skips signal processing, relies on conversation scan.
- **signals.jsonl grows large**: `memory_store.py` prunes >14-day entries on every `append()`. `/reflect` cleanup also prunes.
- **Concurrent sessions**: Each signal has `session_id`. Append interleaving is benign (complete JSON per line).
- **Hook timeout**: PreCompact/SessionEnd cap at last 200 turns. Silent degradation.
- **Empty session**: `/reflect` responds "Nothing to reflect on."
- **All duplicates**: `/reflect` responds "All learnings already captured."
- **settings.json missing**: `/reflect-toggle` creates it with hooks object.

## Out of Scope

| Feature | Rationale |
|---------|-----------|
| SQLite storage | JSONL sufficient at expected volume. Schema designed for mechanical migration. |
| Vector/semantic search | Requires external dependencies. Tags + grep sufficient for v3. |
| Headless Claude analysis | Adds API cost. `/reflect` uses active session. |
| Background worker service | Hooks + skill invocation cover the capture/analysis loop. |
| MCP server | Adds complexity. Pure hooks + skills for v3. |
| Automated skill extraction | Flag candidates only. No auto-generated SKILL.md files. |
| Confidence decay over time | Simple counter sufficient. Time-based decay deferred. |
| Cross-project analytics | Signal format includes project path for future use. |
| Static analysis `/audit-project` | Defer to v3.1. Friction-based detection aligns with zero-overhead philosophy. |
