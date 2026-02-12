# Skills

Curated skills and plugins for Claude Code.

## Plugins

### superpowers

Opinionated development workflows — planning, debugging, TDD, code review, and collaboration patterns. Managed as a [git subtree](#working-with-the-superpowers-subtree) from [obra/superpowers](https://github.com/obra/superpowers).

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

| Skill                            | Description                                            |
| -------------------------------- | ------------------------------------------------------ |
| `brainstorming`                  | Collaborative design exploration before implementation |
| `writing-plans`                  | Comprehensive implementation plans with TDD            |
| `systematic-debugging`           | Observe, hypothesize, test, fix — never guess          |
| `test-driven-development`        | Red-Green-Refactor cycle                               |
| `verification-before-completion` | Prove it works before claiming it does                 |
| `dispatching-parallel-agents`    | Run independent tasks concurrently                     |
| `executing-plans`                | Task-by-task plan execution with checkpoints           |
| `finishing-a-development-branch` | Merge, PR, or cleanup options                          |
| `requesting-code-review`         | Systematic review before merging                       |
| `receiving-code-review`          | Technical rigor when processing feedback               |
| `writing-skills`                 | Guide for creating SKILL.md files                      |
| `subagent-driven-development`    | Subagent per task with code review                     |
| `using-git-worktrees`            | Isolated workspaces for feature work                   |
| `using-superpowers`              | Skill discovery and invocation                         |

### mikro-orm plugin

| Skill       | Description                                               |
| ----------- | --------------------------------------------------------- |
| `mikro-orm` | Entity design, migrations, queries, unit of work, testing |

### Standalone skills

| Skill                 | Description                                                   |
| --------------------- | ------------------------------------------------------------- |
| `self-reflect`        | End-of-session review — batch-proposes learnings to CLAUDE.md |
| `self-reflect-toggle` | Toggle passive self-improvement detection on/off              |

### References/Ideas

- Create a skill for generating new skill based on online documentation and repo scanning
- See [antfu/skills](https://github.com/antfu/skills) for the following ideas
  - Add vendor skills for a curated list of already existing skills
  - Add skill/script for generating new skills based on their repo and only documentation

## Working with the superpowers subtree

The `plugins/superpowers/` directory is a git subtree of [obra/superpowers](https://github.com/obra/superpowers). The upstream remote is named `superpowers-upstream`.

### Making local changes

Edit files in `plugins/superpowers/` and commit normally — no special commands needed. Your changes are regular commits in this repo.

### Pulling upstream changes

```bash
git subtree pull --prefix=plugins/superpowers superpowers-upstream main --squash
```

This fetches the latest from upstream and merges it with your local changes. If both sides touched the same files, you'll get a normal merge conflict to resolve.

### Pushing changes back upstream

If you want to contribute a change back to obra/superpowers:

```bash
git subtree push --prefix=plugins/superpowers superpowers-upstream my-feature-branch
```

This extracts commits that touch `plugins/superpowers/` and pushes them to a branch on the upstream remote (requires push access or a fork).

## License

MIT
