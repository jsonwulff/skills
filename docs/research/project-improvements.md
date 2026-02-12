# Research: Project-Side Improvement Proposals for v3

## Overview

The v3 self-improvement system's most novel aspect is proposing improvements to the **project itself** — not just to Claude's configuration (CLAUDE.md, hooks, skills). Most existing agent self-improvement systems (Reflexion, AGENTS.md-based learning, the v1/v2 systems in this repo) focus exclusively on teaching the agent. But sometimes the project structure is what's holding the agent back: confusing directory layouts, misleading file names, missing documentation, inconsistent conventions. These are problems that would confuse any new contributor — human or AI.

This document catalogs the types of project-side improvements an agent can detect and propose, evaluates detection strategies, recommends a proposal format, and identifies what should ship in v3 vs. what to defer.

---

## 1. Catalog of Project-Side Improvement Types

### 1.1 File/Folder Structure Issues

**What it looks like:**
- Related code scattered across unrelated directories (e.g. API handlers in three different folders)
- Inconsistent directory depth (some features flat, others deeply nested)
- Orphaned directories (empty or containing only deprecated code)
- No clear convention for where new code should go

**How Claude detects it during normal work:**
- Multiple Glob/Grep queries needed to find related code — the agent searches in 2-3 wrong places before finding the right one
- Agent places a new file in one location, user corrects it to a different one
- Agent asks "where should this go?" because no convention is apparent
- Same file type (e.g. tests) found in inconsistent locations across the project

**Example proposal:**
> **Structure**: Test files are inconsistently placed — some in `__tests__/`, some co-located as `.test.ts`, some in a top-level `tests/` directory. Consider standardizing on co-located `.test.ts` files (matching the pattern in `src/components/`).

**Detection signal strength:** High. Navigation friction is directly measurable through tool call patterns.

### 1.2 Naming Inconsistencies

**What it looks like:**
- Files named in mixed conventions (`userService.ts`, `auth-handler.ts`, `OrderProcessor.ts`)
- Functions/variables that don't match their purpose (a function called `process()` that validates)
- Abbreviations used inconsistently (`usr` vs `user`, `cfg` vs `config`)
- File names that don't describe contents (`utils.ts` containing domain logic, `helpers.ts` as a dumping ground)

**How Claude detects it during normal work:**
- Agent opens a file expecting one thing based on its name, but finds something different
- Agent creates a new file and has to guess which naming convention to follow
- Agent misidentifies the purpose of a module from its name alone, leading to incorrect usage

**Example proposal:**
> **Naming**: Service files use three different conventions: camelCase (`userService.ts`), kebab-case (`auth-handler.ts`), and PascalCase (`OrderProcessor.ts`). The most common pattern is camelCase (8 of 12 files). Consider standardizing.

**Detection signal strength:** Medium. Naming confusion is observable but harder to distinguish from agent error.

### 1.3 Missing or Outdated Documentation

**What it looks like:**
- No README or a README that describes a different project state
- Missing API documentation for exported functions
- No setup/onboarding instructions — agent has to reverse-engineer build steps
- Stale comments that describe removed behavior
- No CLAUDE.md or AGENTS.md with project conventions

**How Claude detects it during normal work:**
- Agent fails to find a build/test command and has to probe the environment
- Agent reads a README that contradicts the actual project structure
- Agent encounters undocumented configuration that requires reading source code to understand
- Agent repeatedly asks the user about conventions that should be documented

**Example proposal:**
> **Documentation**: No documented way to run tests. After investigation, the command is `pnpm test:unit` (not the typical `npm test`). Consider adding a `## Commands` section to the project README or CLAUDE.md.

**Detection signal strength:** High. Missing documentation causes measurable friction (extra tool calls, user questions).

### 1.4 Code Organization Issues

**What it looks like:**
- God files: single files with many unrelated exports
- Circular dependencies between modules
- No module boundaries — any file imports from any other file
- Utility functions duplicated across the codebase
- Dead code that hasn't been removed

**How Claude detects it during normal work:**
- Agent opens a "utility" file and finds it has 500+ lines covering 10 unrelated concerns
- Agent encounters import errors due to circular dependencies
- Agent finds two identical helper functions in different modules
- Agent discovers unused exports or unreachable code paths during modification

**Example proposal:**
> **Organization**: `src/utils/helpers.ts` (487 lines) contains date formatting, API response parsing, string manipulation, and auth token handling. Consider splitting into focused modules: `src/utils/date.ts`, `src/utils/api.ts`, `src/utils/auth.ts`.

**Detection signal strength:** Medium. Noticeable during modification but requires judgment about when disorganization crosses the threshold from "fine" to "problematic."

### 1.5 Configuration Issues

**What it looks like:**
- Missing config files that tools expect (`.editorconfig`, `tsconfig.json` paths)
- Outdated package.json scripts that reference removed files
- Inconsistent or missing lint/format configuration
- Build scripts that don't work without undocumented environment setup

**How Claude detects it during normal work:**
- Build/test commands fail due to missing or incorrect configuration
- Linter produces unexpected results because config is missing or outdated
- Agent discovers environment variables are needed but undocumented

**Example proposal:**
> **Configuration**: `package.json` has a `test:e2e` script that references `cypress.config.ts`, but this file doesn't exist. The project appears to have migrated to Playwright (`playwright.config.ts` exists). Consider removing the stale script.

**Detection signal strength:** High. Configuration issues cause direct failures that are unambiguous signals.

### 1.6 Test Structure Issues

**What it looks like:**
- Tests not co-located with the code they test
- Missing test utilities or fixtures — each test file reinvents setup code
- No clear distinction between unit, integration, and e2e tests
- Test files that test multiple unrelated modules

**How Claude detects it during normal work:**
- Agent can't find tests for a module it's modifying
- Agent sees duplicated test setup across many files
- Agent runs all tests when only unit tests were needed (no separation)

**Example proposal:**
> **Tests**: Test files for `src/services/` are in `tests/unit/services/` while tests for `src/components/` are co-located as `.test.tsx`. Consider a single convention — co-location is more common in the codebase (23 vs 8 files).

**Detection signal strength:** Medium. Test structure friction is real but sometimes involves judgment calls about conventions.

---

## 2. Detection Approaches

### 2.1 Friction Signal Capture (Recommended for v3)

**Concept:** Instrument the agent's normal workflow to detect patterns that indicate project-side issues.

**Signals to capture via hooks:**

| Signal | Hook Point | What It Indicates |
|--------|-----------|-------------------|
| Multiple Glob/Grep before finding target | PostToolUse | Unpredictable file structure |
| Agent opens file, immediately opens different file | PostToolUse sequence | Misleading file names |
| Build/test command fails, agent tries alternatives | PostToolUseFailure | Missing/outdated documentation |
| User corrects file placement | PreCompact (conversation analysis) | Undocumented conventions |
| Same file searched for in multiple sessions | Cross-session signal analysis | Recurring navigation confusion |
| Agent reads a file >500 lines | PostToolUse | Possible god file / organization issue |

**Implementation approach:**
- Extend the existing `capture-signals.py` (v2 PreCompact hook) to look for navigation patterns in the tool use transcript
- Add a new signal type: `"type": "friction"` alongside the existing `"correction"` and `"failure"` types
- Store additional metadata: `files_searched`, `files_opened`, `search_queries` to enable pattern analysis in `/reflect`

**Advantages:**
- Zero active-session overhead (hooks are async or fire at compaction boundaries)
- Builds on existing v2 signal infrastructure
- Captures real friction, not hypothetical issues
- Signals accumulate across sessions, building confidence

**Disadvantages:**
- Requires multiple sessions to build confidence for some issues
- Can't detect structural problems the agent never encounters
- Relies on pattern heuristics that may produce false positives

### 2.2 Post-Session Analysis via /reflect (Recommended for v3)

**Concept:** Extend `/reflect` to analyze the current session for project-side friction in addition to agent-side learnings.

**How it works:**
1. After gathering agent-side learnings (existing Step 1), scan for friction patterns:
   - Count distinct search queries per task (high count = poor structure)
   - Identify files opened but not used (misleading names)
   - Identify tool failures related to missing docs or configuration
   - Look for user corrections about where code belongs
2. Classify friction into improvement categories (structure, naming, docs, config, tests)
3. Present project-side proposals separately from CLAUDE.md proposals
4. On approval, write proposals to a project improvements file (not CLAUDE.md — see Section 4)

**Advantages:**
- Uses LLM intelligence for classification (much better than pattern matching alone)
- Natural integration point — users already run `/reflect` at session end
- Can combine hook-captured signals with in-session conversation analysis
- Can reason about whether an issue is worth proposing vs. too minor

**Disadvantages:**
- Only catches issues from the current session (mitigated by cross-session signal accumulation)
- Requires LLM inference at reflection time (but this is already the case for agent-side proposals)

### 2.3 Static Analysis Scan (Defer to v3.1+)

**Concept:** A separate skill (e.g. `/audit-project`) that proactively scans project structure without waiting for friction to occur.

**What it would check:**
- File naming consistency (detect mixed conventions via pattern analysis)
- Directory structure consistency (depth variation, orphaned dirs)
- README vs. actual structure alignment
- Test co-location consistency
- Import graph analysis (circular deps, god modules)
- Stale configuration (scripts referencing missing files)

**Advantages:**
- Catches issues proactively, before they cause friction
- Can provide a comprehensive baseline assessment
- Useful for new projects or projects Claude hasn't worked in before

**Disadvantages:**
- Expensive: requires reading many files and running analysis
- High false positive risk without session context (some "inconsistencies" are intentional)
- Scope creep: hard to know when to stop analyzing
- Not aligned with the v3 "zero overhead" philosophy — this is active analysis

**Recommendation:** Defer. The friction-based approach (2.1 + 2.2) is better aligned with v3's philosophy of passive signal capture. A static analysis scan is valuable but belongs in a later version as an optional, explicitly-invoked skill.

### 2.4 Cross-Session Pattern Detection (Recommended for v3, basic form)

**Concept:** Accumulate friction signals across sessions and detect recurring patterns.

**Implementation:**
- Each session's friction signals are appended to `~/.claude/reflections/signals.jsonl` with project path as metadata
- `/reflect` groups signals by project and looks for:
  - Same file searched for across 3+ sessions → structural confusion
  - Same command failing across sessions → documentation gap
  - Same directory explored and abandoned → misleading organization
- Confidence threshold: only propose project improvements when a pattern appears in 2+ sessions

**Advantages:**
- Much higher confidence than single-session detection
- Filters out one-off confusion vs. systemic issues
- Works with the existing signals.jsonl infrastructure

**Disadvantages:**
- Requires multiple sessions before first proposals (cold start)
- Signal deduplication across sessions adds complexity
- Stale signals from old sessions need cleanup

---

## 3. Recommended Approach for v3

### What to Include

1. **Friction signal capture in hooks** — Extend the v2 `capture-signals.py` to detect navigation friction patterns (multiple searches, file open-and-abandon, build failures). Add `"type": "project_friction"` signals to `signals.jsonl`.

2. **Project-side analysis in /reflect** — Add a new step to `/reflect` (after agent-side proposals) that:
   - Reviews friction signals tagged as `project_friction`
   - Scans the session conversation for structural confusion moments
   - Classifies issues by category (structure, naming, docs, config, tests)
   - Presents project improvement proposals separately from CLAUDE.md proposals

3. **Basic cross-session accumulation** — Friction signals persist in `signals.jsonl`. `/reflect` considers signals from previous sessions when building confidence for project-side proposals.

4. **Project improvements file** — Write approved proposals to `.claude/improvements.md` (see Section 4 for format). This is distinct from CLAUDE.md because these are proposals for actual project changes, not agent instructions.

### What to Defer

| Feature | Reason to Defer |
|---------|----------------|
| Static analysis `/audit-project` skill | Active analysis contradicts zero-overhead philosophy; needs its own design cycle |
| Automated refactoring | Too risky without explicit user initiation; v3 proposes, doesn't execute |
| Import graph analysis | Requires language-specific tooling; not generalizable across projects |
| Cross-project pattern transfer | "Project X had this layout and it worked well" — requires much more memory infrastructure |
| Integration with beads or external trackers | Adds dependency; v3 should be self-contained first |
| Confidence decay / signal aging | Nice to have but adds complexity; simple 30-day TTL on signals is sufficient for v3 |

---

## 4. Proposal Format Design

### The Problem with CLAUDE.md for Project Improvements

CLAUDE.md entries teach Claude how to work with the project as-is: "run `pnpm test`", "handlers go in `src/handlers/`". Project improvement proposals are fundamentally different — they describe how the project **should change**. Writing "consider renaming X to Y" in CLAUDE.md is awkward because:

- It mixes instructions (do this) with suggestions (consider this)
- It clutters CLAUDE.md with potentially stale proposals
- It doesn't track whether the improvement was applied, deferred, or rejected

### Recommended Format: `.claude/improvements.md`

A separate file in the project's `.claude/` directory that tracks proposed improvements.

```markdown
# Project Improvements

Proposed by `/reflect` — review and apply at your pace.

## Pending

### [2026-02-11] Standardize test file location
- **Category**: Test structure
- **Impact**: Medium — reduces confusion when finding/creating tests
- **Details**: Test files use two conventions: co-located `.test.ts` (23 files in `src/components/`) and separate `tests/unit/` directory (8 files for `src/services/`). Standardizing on co-location matches the majority pattern and aligns with modern best practices.
- **Suggested action**: Move `tests/unit/services/*.test.ts` to be co-located with their source files in `src/services/`.
- **Confidence**: High (observed in 3 sessions)

### [2026-02-11] Document build commands
- **Category**: Documentation
- **Impact**: High — agent and new contributors waste time discovering commands
- **Details**: No README section documents how to build, test, or run the project. The commands are `pnpm dev`, `pnpm test:unit`, `pnpm build`.
- **Suggested action**: Add a `## Development` section to README.md with these commands.
- **Confidence**: High (build command discovery failed in 2 sessions)

## Applied

### [2026-02-08] Standardize service file naming
- **Applied**: 2026-02-09
- **Details**: Renamed 4 service files from mixed case to consistent camelCase.

## Deferred

### [2026-02-05] Split utils/helpers.ts
- **Reason**: "Too much churn right now, will do after release" — user, 2026-02-05
```

### Format Properties

| Property | Value | Rationale |
|----------|-------|-----------|
| **Location** | `.claude/improvements.md` | Co-located with `.claude/CLAUDE.md`; git-tracked; visible to all project contributors |
| **Format** | Markdown with structured sections | Human-readable; easy to edit; parseable by `/reflect` for dedup |
| **Sections** | Pending / Applied / Deferred | Tracks lifecycle without complex tooling |
| **Entry fields** | Date, Category, Impact, Details, Suggested action, Confidence | Enough context to act on; not so much that it's burdensome to generate |
| **Confidence** | Low/Medium/High | Based on number of sessions with corroborating friction signals |
| **Impact** | Low/Medium/High | Estimated effect on agent and developer productivity |

### Quick Wins vs. Large Refactors

The proposal format includes an **Impact** field and a **Suggested action** that implicitly signals scope:

- **Quick wins** (High impact, simple action): "Add a `## Commands` section to README.md" — single file, 5 minutes
- **Medium refactors** (Medium impact, moderate action): "Move 8 test files to co-locate with source" — mechanical, low risk
- **Large refactors** (Variable impact, complex action): "Split `helpers.ts` into focused modules" — requires thought about API boundaries

`/reflect` should favor proposing quick wins. Large refactors should only be proposed when friction signals are very strong (high confidence, high frequency) and should be framed as suggestions, not instructions.

---

## 5. Prior Art and Influences

### Factory.ai: Linters as Agent Guides

Factory's approach treats linters as the primary mechanism for encoding project standards for agents. Key insight: **"Glob-ability"** — making file structure predictable so agents can reliably place, find, and refactor code. Their framework pairs human-written AGENTS.md (the "why") with machine-enforceable lint rules (the "how"). For v3, this suggests that project-side improvements should target glob-ability and predictability — the same qualities that make a codebase navigable for both agents and humans.

### Beads (steveyegge/beads): Graph-Based Task Tracking

Beads provides a git-backed, graph-structured issue tracker designed for AI agent memory. Key features relevant to project improvements:
- **Hash-based IDs** that prevent merge collisions in multi-agent workflows
- **Relationship types**: `blocks`, `relates_to`, `duplicates`, `supersedes` — could model dependencies between improvement proposals
- **Auto-ready detection**: identifies tasks with no open blockers
- **Semantic memory decay**: summarizes completed items to conserve context

For v3, beads' data model is more complex than needed. But the concept of tracking improvement proposals with dependency relationships is valuable — e.g. "standardize test location" blocks "add test coverage CI check." The `.claude/improvements.md` format is a deliberately simpler starting point that could evolve toward beads-like structure if needed.

### Reflexion / Self-Correcting Agents

The Reflexion framework stores "self-reflections" (textual analysis of what went wrong) in long-term memory and provides them as context for future attempts. This maps directly to v3's friction signal approach: capture what went wrong (friction signals), analyze it (in `/reflect`), and persist the insight (in `improvements.md` or CLAUDE.md). The key difference is that v3 distinguishes between agent-side reflections (CLAUDE.md: "next time do X") and project-side reflections (improvements.md: "the project should change Y").

### Addy Osmani: Self-Improving Code Agents

Osmani's framework uses a four-channel persistence system: AGENTS.md, git history, progress.txt, and a task list. The insight for v3 is the separation between **knowledge persistence** (AGENTS.md, analogous to our CLAUDE.md) and **work tracking** (progress.txt / tasks, analogous to our improvements.md). Agent learning and project improvement proposals serve different purposes and should live in different files.

### Propel: AI-Friendly Codebase Structure

Propel's research found that 65% of developers experience "missing context" during refactoring and 60% during test generation. Their concept of **"context rot"** — gradual degradation of documentation, specifications, and structural consistency — is exactly what v3's project-side detection aims to catch early. Their recommendation to validate AGENTS.md in CI/CD is a good future extension.

### Code Smell Detection (iSMELL, SonarQube)

Traditional code smell detection uses AST analysis and heuristic rules. The LLM-based approach (iSMELL) uses a Mixture of Experts architecture for detection and LLMs for refactoring suggestions. For v3, AST-level analysis is too heavy and language-specific. But the conceptual framework of "smells" — indicators that something is suboptimal without being strictly wrong — maps well to project structure issues. The v3 system detects "structural smells" through friction signals rather than static analysis.

---

## 6. Open Questions

### Detection Boundary
**Where does project-side improvement detection end and a full project management tool begin?** The v3 system should detect issues that cause agent friction, not attempt to be a comprehensive project quality tool. But the line is blurry — a suggestion to "add API documentation" could be an agent friction fix or a general project quality suggestion. Proposed heuristic: only propose improvements that the agent has directly experienced friction with. If Claude has never needed the API docs, don't propose adding them.

### User Fatigue
**Will users find project improvement proposals annoying?** Unlike CLAUDE.md entries (which are small, additive, and immediately useful), project improvements require the user to do actual work. If `/reflect` proposes 5 file renames and a directory restructure every session, users may disable the feature. Proposed mitigation: strict confidence thresholds (2+ sessions of friction before proposing), impact-based prioritization (propose one high-impact improvement, not five low-impact ones), and a "Defer" action that suppresses re-proposal.

### Scope of "Suggested Action"
**How specific should the suggested action be?** "Consider standardizing test location" is vague. "Move `tests/unit/services/auth.test.ts` to `src/services/auth.test.ts`" is concrete but potentially wrong about details. Proposed approach: be concrete about the pattern and the first example, but frame the full scope as the user's decision. "Move test files to co-locate with source (e.g. `tests/unit/services/auth.test.ts` → `src/services/auth.test.ts`). 8 files total."

### Execution Assistance
**Should `/reflect` offer to execute approved project improvements?** This crosses from "propose" to "act" and raises risk. A renamed file might break imports across the codebase. Proposed approach for v3: propose only, never execute automatically. A future `/improve` skill could handle execution with proper dry-run and rollback support.

### Cross-Project Learning
**Can friction patterns from one project inform proposals for another?** E.g., "projects with co-located tests tend to cause less agent friction." This is valuable but requires a level of abstraction and cross-project memory that is beyond v3 scope. The signal storage format should not preclude this — including project path in each signal enables future cross-project analysis.

### Interaction with Existing Linters
**Should the system be aware of existing lint/format configuration?** If a project already has ESLint rules for naming conventions, proposing naming standardization may be redundant or contradictory. Proposed approach: when proposing naming/style improvements, check for the existence of relevant config files (`.eslintrc`, `.prettierrc`, `biome.json`) and mention them in the proposal context.

---

## 7. Summary of Recommendations

| Decision | Recommendation |
|----------|---------------|
| **Primary detection mechanism** | Friction signal capture via hooks + `/reflect` analysis |
| **Signal types to add** | `project_friction` with sub-categories: navigation, naming, docs, config, tests |
| **Cross-session detection** | Yes, basic form — accumulate signals in `signals.jsonl`, analyze in `/reflect` |
| **Static analysis scan** | Defer to v3.1+ as optional `/audit-project` skill |
| **Proposal storage** | `.claude/improvements.md` — separate from CLAUDE.md |
| **Proposal lifecycle** | Pending → Applied / Deferred (user-managed) |
| **Execution** | Propose only — no auto-execution in v3 |
| **Confidence threshold** | Require 2+ sessions of corroborating friction before proposing structural changes |
| **Proposal cadence** | Max 2-3 project improvement proposals per `/reflect` run, prioritized by impact |
| **Quick wins vs. refactors** | Favor quick wins; propose large refactors only with high confidence + high frequency |
| **Beads integration** | Defer — the markdown format is sufficient for v3; evaluate beads for v3.1+ if proposal tracking becomes complex |
