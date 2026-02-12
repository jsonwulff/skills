---
name: self-reflect
description: "Review learning moments from this session and propose improvements to CLAUDE.md or .claude/improvements.md."
disable-model-invocation: true
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
