---
name: subagent-driven-development
description: "Use when executing implementation plans with independent tasks in the current session"
---

# Subagent-Driven Development

<!-- TODO: Customize — based on obra/superpowers -->

## Overview

Execute an implementation plan by dispatching a fresh subagent per task, with code review between each.

## Process

1. Read the plan
2. For each task: dispatch a subagent to implement it
3. Review the subagent's output
4. If good: commit and move to next task
5. If not: fix or re-dispatch
