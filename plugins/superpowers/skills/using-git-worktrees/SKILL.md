---
name: using-git-worktrees
description: "Use when starting feature work that needs isolation from current workspace — creates isolated git worktrees"
---

# Using Git Worktrees

<!-- TODO: Customize — based on obra/superpowers -->

## Overview

Create isolated git worktrees for feature work so you don't pollute the main working directory.

## Process

1. Create a new branch
2. Create a worktree: `git worktree add ../project-feature feature-branch`
3. Work in the worktree directory
4. When done: merge and clean up with `git worktree remove`
