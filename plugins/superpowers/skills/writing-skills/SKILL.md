---
name: writing-skills
description: "Use when creating new skills, editing existing skills, or verifying skills work before deployment"
---

# Writing Skills

<!-- TODO: Customize — based on obra/superpowers -->

## Overview

Guide for creating effective SKILL.md files.

## Structure

```markdown
---
name: kebab-case-name
description: "Clear trigger description — Claude uses this to decide when to activate"
---

# Skill Title

## Overview
What this skill does and when to use it.

## Process
Step-by-step instructions.

## Rules
Hard constraints to follow.
```

## Tips

- Description is the most important field — make it specific
- Keep under 500 lines — use reference.md for details
- Test with `/skill-name` to verify it loads
