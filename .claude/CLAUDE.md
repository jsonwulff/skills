# Skills Repo

Monorepo for Claude Code plugins. Each plugin lives under `plugins/<name>/`.

## Plugins

- **self-improvement** — `plugins/self-improvement/` — Hook-driven learning signal capture + `/reflect` review skill
- **superpowers** — `plugins/superpowers/` — Workflow skills (TDD, debugging, brainstorming, planning, etc.)
- **mikro-orm** — `plugins/mikro-orm/` — MikroORM skill

## Plugin Structure

```
plugins/<name>/
├── .claude-plugin/plugin.json   # metadata, version, skill list
├── hooks/hooks.json             # auto-registered hooks (optional)
└── skills/<skill-name>/
    ├── SKILL.md                 # skill instructions
    ├── hooks/                   # hook scripts (optional)
    ├── scripts/                 # bundled scripts (optional)
    └── references/              # reference docs (optional)
```

Hooks in `hooks/hooks.json` auto-register when the plugin is enabled. Use `${CLAUDE_PLUGIN_ROOT}` for portable paths to scripts.

## Installed Location

When installed globally, plugins are cached at `~/.claude/plugins/cache/skills/<name>/<version>/`.
