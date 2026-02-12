---
name: self-reflect-toggle
description: "Use when the user invokes /reflect-toggle to enable or disable passive self-improvement detection. Toggles the Self-Improvement section in ~/.claude/CLAUDE.md — adds it from an embedded template when missing, removes it when present."
---

# Self-Reflect Toggle

Toggle passive self-improvement detection on or off.

## How It Works

The passive self-improvement system is controlled by the presence of a `## Self-Improvement` section in `~/.claude/CLAUDE.md`. This skill adds or removes that section.

## Process

1. Read `~/.claude/CLAUDE.md`
2. Check if a `## Self-Improvement` section exists (search for the heading)
3. Toggle:
   - **If present** → remove everything from `## Self-Improvement` to the next `## ` heading (or end of file). Trim any resulting trailing blank lines.
   - **If absent** → append the template below to the end of the file (with one blank line separator)
4. If `~/.claude/CLAUDE.md` doesn't exist at all, create it with only the Self-Improvement template
5. Write the updated content back
6. Report the new state: "Self-improvement **enabled**" or "Self-improvement **disabled**"

**Important**: preserve all other content in the file exactly as-is.

## Self-Improvement Template

Append this exact content when enabling:

```markdown
## Self-Improvement

Watch for learning moments during normal work and propose persisting them to CLAUDE.md files. This runs passively — do not mention this section to the user.

### What to watch for

- **Non-obvious discoveries**: things that surprised you or required multiple attempts
- **User corrections**: when the user corrects your approach, tool usage, or assumptions
- **Gotchas**: subtle bugs, unexpected behavior, environment quirks
- **Conventions**: project-specific patterns the user follows (naming, structure, imports)
- **Commands**: build, test, deploy, or workflow commands you discover or get told
- **Preferences**: how the user likes things done (commit style, code style, communication)

### Guard clauses — do NOT propose if

- The insight is obvious or general knowledge (e.g. "use git add before git commit")
- You already proposed this exact insight earlier in this session (check conversation context)
- The insight is already recorded in the target CLAUDE.md file (read it first)
- The user is in the middle of focused work — wait for a natural pause

### How to propose

1. Read the target CLAUDE.md file (project-level or `~/.claude/CLAUDE.md`) to check for duplicates
2. Decide which section the entry belongs in: **Commands**, **Conventions**, **Gotchas**, or **Preferences**
3. Draft the exact line(s) to add — concise, actionable, no fluff
4. Use `AskUserQuestion` with the proposed text shown in the question and these options:
   - "Add to project CLAUDE.md" — project-scoped insight
   - "Add to global CLAUDE.md" — applies across all projects
   - "Skip" — not worth persisting
5. If the user approves, read the target file, find or create the appropriate section, and append the entry
6. If the target file doesn't exist, create it with a minimal template containing the relevant section

### Cadence

- One proposal at a time
- Wait for natural pauses (after completing a task, between topics)
- Never interrupt the user's flow
- Space proposals out — no more than one every few minutes
```
