---
name: self-reflect-toggle
description: "Enable or disable the self-improvement signal capture hooks."
disable-model-invocation: true
---

# Self-Reflect Toggle

Toggle the self-improvement signal capture system on or off.

## How It Works

The self-improvement system uses Claude Code hooks to silently capture learning signals during normal work. This skill adds or removes those hooks from `~/.claude/settings.json`.

When enabled, four hooks are active:
- **PreCompact** — Mines the transcript for corrections, conventions, and patterns before compaction
- **PostToolUseFailure** — Logs tool failures as learning signal candidates (async)
- **SessionEnd** — Extracts a lightweight session summary
- **SessionStart** (compact) — Re-injects captured signals after context compaction

## Process

### 1. Detect plugin install path

Determine the absolute path to the `hooks/` directory within this plugin. The hooks directory is at `self-reflect/hooks/` relative to this skill's parent directory. Resolve to an absolute path — this is needed for the hook commands in settings.json.

To find it: this SKILL.md is at `<plugin-root>/skills/self-reflect-toggle/SKILL.md`. The hooks are at `<plugin-root>/skills/self-reflect/hooks/`. Use Bash to resolve the absolute path:
```bash
PLUGIN_ROOT="$(cd "$(dirname "<path-to-this-SKILL.md>")/../../skills/self-reflect/hooks" && pwd)"
```

### 2. Read current settings

Read `~/.claude/settings.json`. If it doesn't exist, start with an empty object `{}`.

### 3. Detect current state

Check if any hook entries in `settings.json` have commands containing `self-reflect` in the path. If found, the system is currently **enabled**.

### 4. Toggle

#### If currently enabled → Disable

1. Remove all hook entries from `PreCompact`, `PostToolUseFailure`, `SessionEnd`, and `SessionStart` arrays where the command contains `self-reflect`
2. If removing an entry leaves an empty array, remove the entire key
3. Preserve all other hooks (e.g., Notification hooks)
4. Write updated `settings.json`
5. Report: "Self-improvement **disabled** — hooks removed. Changes take effect on next session or after `/hooks` review."

#### If currently disabled → Enable

1. Create `~/.claude/reflections/` directory if it doesn't exist
2. Add these hook entries to `settings.json`, merging with any existing hooks:

```json
{
  "hooks": {
    "PreCompact": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"<HOOKS_DIR>/capture-signals.py\"",
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
            "command": "bash \"<HOOKS_DIR>/capture-failure.sh\"",
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
            "command": "python3 \"<HOOKS_DIR>/capture-session-summary.py\"",
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
            "command": "bash \"<HOOKS_DIR>/inject-signals.sh\""
          }
        ]
      }
    ]
  }
}
```

Replace `<HOOKS_DIR>` with the absolute path detected in step 1.

3. When merging, preserve existing hook entries under each event key. Append the new entries to existing arrays, do not replace them.
4. Write updated `settings.json`
5. Report: "Self-improvement **enabled** — 4 hooks added. Restart your session or run `/hooks` to review."

### 5. Verify hooks directory

After toggling, verify the hooks directory exists and contains the expected scripts:
- `capture-signals.py`
- `capture-failure.sh`
- `capture-session-summary.py`
- `inject-signals.sh`
- `memory_store.py`

If any are missing, warn: "Warning: hook script `<name>` not found at `<path>`. The hook may fail at runtime."

## Edge Cases

- **settings.json doesn't exist**: Create it with just the hooks object when enabling. Create `{}` as base.
- **settings.json has no hooks key**: Add the hooks key when enabling.
- **Other hooks exist**: Always preserve them. Only add/remove entries with `self-reflect` in the command path.
- **Partial state** (some hooks present, others missing): Treat as enabled. Disable removes all self-reflect hooks. Re-enable adds the full set.
- **hooks directory not found**: Report error and do not add hooks. Suggest reinstalling the plugin.
