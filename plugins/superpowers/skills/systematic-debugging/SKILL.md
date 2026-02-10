---
name: systematic-debugging
description: "Use when encountering any bug, test failure, or unexpected behavior, before proposing fixes"
---

# Systematic Debugging

<!-- TODO: Customize with your own debugging workflow -->
<!-- Based on obra/superpowers — replace this with your forked version -->

## Overview

Systematic approach to debugging. Observe, hypothesize, test, fix. Never guess.

## The Process

1. **Reproduce** — confirm the bug exists and get exact error output
2. **Observe** — read the relevant code, logs, stack traces
3. **Hypothesize** — form 2-3 theories about root cause
4. **Test hypotheses** — add logging, write a failing test, or isolate the issue
5. **Fix** — make the minimal change to fix the root cause
6. **Verify** — run the original repro case and existing tests
7. **Commit** — commit the fix with a descriptive message

## Rules

- **Never guess** — always verify your hypothesis before changing code
- **One change at a time** — don't fix multiple things at once
- **Write a failing test first** — proves the bug exists, prevents regression
- **Minimal fix** — don't refactor while debugging
- **Read before writing** — understand the code before changing it
