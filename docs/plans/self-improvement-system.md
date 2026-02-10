# Self-Improvement System for Claude Code

## Context

Claude Code has no mechanism to learn from sessions and persist insights for future use. When it discovers project conventions, gets corrected by the user, or hits non-obvious gotchas, those learnings are lost when the session ends. This system adds automatic learning-moment detection with user-controlled persistence to CLAUDE.md files.

## Architecture

Three components working together:

1. **Passive detection** — Instructions in `~/.claude/CLAUDE.md` that are always loaded, making Claude watch for learning moments and propose additions via `AskUserQuestion`
2. **Manual reflection** — A `/reflect` skill for comprehensive end-of-session review
3. **Toggle** — A `/reflect-toggle` skill that enables/disables passive detection by adding/removing the CLAUDE.md section

Deduplication is handled naturally through conversation context (no external state needed).

## Files to Create

### 1. `~/.claude/CLAUDE.md` (new file)

Global instructions file with a `## Self-Improvement` section containing:
- Categories to watch for: non-obvious discoveries, user corrections, gotchas, conventions, commands, preferences
- Guard clauses: only propose genuinely non-obvious things, not already proposed this session, not already in target file
- Proposal flow: read target CLAUDE.md first, show exact text, use `AskUserQuestion` with three options (add to project / add to global / skip)
- Target sections: Commands, Conventions, Gotchas, Preferences
- Cadence rule: wait for natural pauses, one proposal at a time, never interrupt flow

### 2. `~/.claude/skills/self-reflect/SKILL.md` (new skill)

Manual `/reflect` skill with this process:
1. **Gather** — Scan full conversation for learning moments across all categories
2. **Deduplicate** — Check conversation context first (skip already-proposed), then read target CLAUDE.md files (skip already-recorded)
3. **Classify** — Sort by scope (global vs project) and category (Commands/Conventions/Gotchas/Preferences)
4. **Present** — Show batch proposals grouped by scope, with exact text to be added
5. **Approve** — `AskUserQuestion` per scope-batch: "Add all" / "Let me pick" / "Skip all"
6. **Write** — Append approved entries to appropriate sections; create file with minimal template if it doesn't exist

Edge cases handled:
- No project open → skip project-scoped proposals
- Empty conversation → "Nothing to reflect on"
- All duplicates → "All learnings already captured"
- No project CLAUDE.md → create at `.claude/CLAUDE.md` (matching user's existing convention) if user approves
- Multiple projects in one session → group by project

### 3. `~/.claude/skills/self-reflect-toggle/SKILL.md` (new skill)

Toggle skill that:
- Reads `~/.claude/CLAUDE.md`
- If `## Self-Improvement` section exists → removes it (disable)
- If section is missing → appends it from embedded template (enable)
- Preserves all other content in the file
- Reports new state to user

The full Self-Improvement template is embedded in the skill so it's self-contained.

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Section presence IS the toggle | No config file needed; the instructions must be in CLAUDE.md to work, so their presence is the natural on/off state |
| Conversation context for session dedup | Free, automatic, session-scoped — no file I/O or cleanup needed |
| Single proposals (passive) vs batch (manual) | During work: minimal interruption. End of session: comprehensive review is expected |
| Template embedded in toggle skill | Self-contained; no sync issues between toggle and initial CLAUDE.md |
| `.claude/CLAUDE.md` for new project files | Matches user's existing convention across all three projects |

## Verification

1. Start a new session in a project → work on something → get corrected → verify passive detection proposes an addition with the three options
2. In the same session, trigger the same insight again → verify no re-proposal
3. Run `/reflect` → verify it skips already-proposed items and presents remaining as batch
4. Run `/reflect-toggle` → verify section removed, other content preserved → run again → verify section restored
5. Accept a proposal for a project without CLAUDE.md → verify file created at `.claude/CLAUDE.md` with proper structure
