# Status Line: Pending Learnings Count

Show the number of pending learning signals in your Claude Code status bar so you know when to run `/reflect`.

## What it shows

When signals have been captured by hooks but not yet reviewed:
```
reflect: 5 pending
```

When no signals are pending, the status line shows nothing (empty string).

## Setup

### 1. Locate memory_store.py

Find the absolute path to `memory_store.py` in your plugin installation. It's in the `self-reflect/hooks/` directory. For example:

```
~/.claude/plugins/cache/<plugin-path>/skills/self-reflect/hooks/memory_store.py
```

You can find it by running:
```bash
find ~/.claude -name "memory_store.py" -path "*/self-reflect/*" 2>/dev/null
```

### 2. Add to settings.json

Open `~/.claude/settings.json` and add or update the `statusLine` key:

```json
{
  "statusLine": {
    "type": "command",
    "command": "python3 \"/absolute/path/to/hooks/memory_store.py\" stats --format statusline"
  }
}
```

Replace `/absolute/path/to/hooks/memory_store.py` with the actual path from step 1.

### 3. Combine with existing status line

If you already have a status line command, you can combine them in a wrapper script. Create `~/.claude/statusline-wrapper.sh`:

```bash
#!/usr/bin/env bash

# Your existing status line output
EXISTING=$(<your-existing-command> 2>/dev/null || echo "")

# Pending learnings count
MEMORY_STORE="/absolute/path/to/hooks/memory_store.py"
REFLECT=$(python3 "$MEMORY_STORE" stats --format statusline 2>/dev/null || echo "")

# Combine (pipe-separated)
PARTS=()
[ -n "$EXISTING" ] && PARTS+=("$EXISTING")
[ -n "$REFLECT" ] && PARTS+=("$REFLECT")

IFS='|' ; echo "${PARTS[*]}"
```

Then set your statusLine to:
```json
{
  "statusLine": {
    "type": "command",
    "command": "bash ~/.claude/statusline-wrapper.sh"
  }
}
```

## Customization

The `memory_store.py stats --format statusline` command outputs:
- `reflect: N pending` when there are `N` signals with status `captured` or `analyzed`
- Empty string when there are no pending signals

To customize the format, you can wrap the command:
```bash
COUNT=$(python3 /path/to/memory_store.py stats --format statusline 2>/dev/null)
[ -n "$COUNT" ] && echo "🔍 $COUNT"
```
