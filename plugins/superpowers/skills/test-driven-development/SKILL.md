---
name: test-driven-development
description: "Use when implementing any feature or bugfix, before writing implementation code"
---

# Test-Driven Development

<!-- TODO: Customize with your own TDD workflow -->
<!-- Based on obra/superpowers — replace this with your forked version -->

## Overview

Red-Green-Refactor. Write the test first, watch it fail, write minimal code to pass, refactor.

## The Cycle

1. **Red** — Write a failing test that describes the desired behavior
2. **Run** — Verify the test fails for the expected reason
3. **Green** — Write the minimum code to make the test pass
4. **Run** — Verify the test passes
5. **Refactor** — Clean up while keeping tests green
6. **Commit** — Commit after each green cycle

## Rules

- **Never write production code without a failing test**
- **Only write enough test to fail** — one assertion per cycle
- **Only write enough code to pass** — resist the urge to generalize early
- **Refactor only when green** — never change behavior and structure at the same time
- **Commit after each cycle** — small, frequent commits
