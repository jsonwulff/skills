---
name: self-reflect
description: "Use when the user invokes /reflect to do a comprehensive end-of-session review. Scans the full conversation for learning moments, deduplicates against already-proposed items and existing CLAUDE.md files, and batch-proposes additions organized by scope (global vs project) and category."
---

# Self-Reflect

Comprehensive end-of-session review of learning moments from the conversation.

## Process

### 1. Gather

Scan the full conversation for learning moments across all categories:

- **Commands**: build, test, deploy, lint, or workflow commands discovered or shared
- **Conventions**: project patterns (naming, structure, imports, architecture)
- **Gotchas**: subtle bugs, unexpected behavior, environment quirks, non-obvious fixes
- **Preferences**: user workflow preferences, commit style, communication style

### 2. Deduplicate

For each candidate:

1. **Check conversation context** — skip if you already proposed this insight earlier via the passive self-improvement system or a previous `/reflect` in this session
2. **Read target CLAUDE.md files** — skip if the insight is already recorded
   - Global: `~/.claude/CLAUDE.md`
   - Project: `CLAUDE.md` or `.claude/CLAUDE.md` in the project root

### 3. Classify

Sort remaining candidates by:

- **Scope**: global (applies across projects) vs project (specific to current project)
- **Category**: Commands, Conventions, Gotchas, Preferences

If working across multiple projects in one session, group project-scoped items by project.

### 4. Present

Show batch proposals grouped by scope. For each group, display:

```
## Global additions

### Gotchas
- `npm ci` silently succeeds with mismatched lockfile on Node 18

### Preferences
- Prefer short commit messages in imperative mood

## Project additions (project-name)

### Commands
- `make dev` starts the dev server with hot reload on port 3000

### Conventions
- All API handlers go in `src/handlers/` with `<resource>.handler.ts` naming
```

### 5. Approve

Use `AskUserQuestion` once per scope-batch:

- **"Add all"** — append every entry in this batch
- **"Let me pick"** — follow up with individual yes/no per entry
- **"Skip all"** — discard this batch

### 6. Write

For each approved entry:

1. Read the target CLAUDE.md file
2. Find the matching section header (e.g. `## Commands`, `## Gotchas`)
3. Append the entry under that section
4. If the section doesn't exist, create it at the end of the file
5. If the file doesn't exist, create it with a minimal template:

```markdown
# Project Name

## Commands

## Conventions

## Gotchas

## Preferences
```

For project-level files, create at `.claude/CLAUDE.md` relative to the project root.

## Edge Cases

- **No project open** (running from `~` or similar): skip project-scoped proposals entirely, only propose global additions
- **Empty or trivial conversation**: respond with "Nothing to reflect on — no learning moments found in this session."
- **All duplicates**: respond with "All learnings from this session are already captured in your CLAUDE.md files."
- **No project CLAUDE.md exists**: ask the user before creating one — include the path in the `AskUserQuestion`
- **Multiple projects touched**: group proposals by project and present each group separately
