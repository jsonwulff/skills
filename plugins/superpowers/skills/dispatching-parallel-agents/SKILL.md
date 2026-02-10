---
name: dispatching-parallel-agents
description: "Use when facing 2+ independent tasks that can be worked on without shared state or sequential dependencies"
---

# Dispatching Parallel Agents

<!-- TODO: Customize — based on obra/superpowers -->

## Overview

When you have multiple independent tasks, dispatch them as parallel subagents for faster execution.

## When to Use

- Tasks have no shared state
- Tasks don't depend on each other's output
- Each task is self-contained

## Process

1. Identify independent tasks
2. Dispatch each as a subagent via the Task tool
3. Wait for results
4. Integrate and verify
