# Skills

Curated skills and plugins for Claude Code.

## Plugins

### superpowers

Opinionated development workflows — planning, debugging, TDD, code review, and collaboration patterns. Forked from [obra/superpowers](https://github.com/obra/superpowers).

### mikro-orm

MikroORM entity design, migrations, query patterns, and best practices for TypeScript database layers.

## Installation

### Claude Code (plugin system)

```bash
# Add the marketplace (one time)
/plugin marketplace add your-org/skills

# Install a specific plugin
/plugin install superpowers
/plugin install mikro-orm
```

### Vercel Skills CLI (cross-agent)

```bash
# Install all skills
npx skills add your-org/skills

# Install a specific skill
npx skills add your-org/skills -s mikro-orm

# Install to a specific agent
npx skills add your-org/skills -s mikro-orm -a claude-code

# Preview available skills
npx skills add your-org/skills -l
```

## Available Skills

### superpowers plugin

| Skill | Description |
|-------|-------------|
| `brainstorming` | Collaborative design exploration before implementation |
| `writing-plans` | Comprehensive implementation plans with TDD |
| `systematic-debugging` | Observe, hypothesize, test, fix — never guess |
| `test-driven-development` | Red-Green-Refactor cycle |
| `verification-before-completion` | Prove it works before claiming it does |
| `dispatching-parallel-agents` | Run independent tasks concurrently |
| `executing-plans` | Task-by-task plan execution with checkpoints |
| `finishing-a-development-branch` | Merge, PR, or cleanup options |
| `requesting-code-review` | Systematic review before merging |
| `receiving-code-review` | Technical rigor when processing feedback |
| `writing-skills` | Guide for creating SKILL.md files |
| `subagent-driven-development` | Subagent per task with code review |
| `using-git-worktrees` | Isolated workspaces for feature work |
| `using-superpowers` | Skill discovery and invocation |

### mikro-orm plugin

| Skill | Description |
|-------|-------------|
| `mikro-orm` | Entity design, migrations, queries, unit of work, testing |

## License

MIT
