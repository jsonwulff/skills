# Research Team Design: Self-Improvement System v3

## How to Use

Copy the kickoff prompt at the bottom into a new Claude Code session. It will create a team with 4 research agents working in parallel, each focusing on a different aspect of the design space. Results get written to `docs/research/` for synthesis.

## Team Structure

```
Team Lead (you)
├── memory-architect     — Memory storage, formats, retrieval patterns
├── signal-researcher    — Learning recognition, signal capture, hook strategies
├── project-improver     — Project-side improvements, structural analysis
└── approach-synthesizer — Cross-cutting: compare all references, propose unified design
```

### Agent 1: `memory-architect`
**Type**: `general-purpose`
**Focus**: Design questions #2 (memory architecture), #5 (cross-session learning), #6 (retrieval)

**Prompt**:
```
You are researching memory architectures for a Claude Code self-improvement system. Your goal is to compare approaches and recommend a storage + retrieval design.

Read the project document at docs/plans/self-improvement-system-v3.md for full context.

Research these specific questions:

1. **Storage format comparison**: Compare JSONL append log, structured markdown files (.learnings/), and SQLite for storing learning signals. Consider: simplicity, queryability, future extensibility (could a dashboard read this?), git-friendliness, concurrent session safety. Look at how these references handle it:
   - claude-mem uses SQLite + FTS5: https://github.com/thedotmack/claude-mem (fetch the README)
   - pskoett uses structured markdown files: https://raw.githubusercontent.com/pskoett/pskoett-ai-skills/main/skills/self-improvement/SKILL.md
   - agent-playbook uses JSON files per memory type: https://raw.githubusercontent.com/zhaono1/agent-playbook/main/skills/self-improving-agent/SKILL.md
   - beads uses Dolt (versioned SQL) + JSONL: https://github.com/steveyegge/beads

2. **Cross-session accumulation**: How do learnings build up over time without becoming stale or noisy? Research confidence scoring (agent-playbook does this), deduplication strategies, and memory decay/pruning.

3. **Retrieval patterns**: When the /reflect skill runs, how should it query memory? Full file scan works for small datasets but won't scale. Research progressive disclosure (claude-mem's 3-layer approach), indexed retrieval, and what "good enough for v3" looks like vs. what needs vector search later.

4. **Extensibility boundary**: Design the storage format so it works with native Python/bash today but a future analytics dashboard or semantic search layer could plug in without migration. What does that interface look like?

Also search the web for "claude code memory system 2025 2026" and "AI agent persistent memory architecture" for any additional approaches worth considering.

Write your findings to docs/research/memory-architecture.md with:
- Comparison table of approaches
- Recommended approach for v3 with rationale
- Migration path to richer tooling
- Open questions or risks
```

### Agent 2: `signal-researcher`
**Type**: `general-purpose`
**Focus**: Design questions #1 (learning recognition), #3 (signal capture points)

**Prompt**:
```
You are researching how to detect learning moments in Claude Code sessions. Your goal is to catalog recognition strategies and recommend a capture approach.

Read the project document at docs/plans/self-improvement-system-v3.md for full context. Also read the v2 plan at docs/plans/self-improvement-system-v2.md which has an initial approach using keyword heuristics.

Research these specific questions:

1. **Learning recognition strategies**: How do you know something is worth remembering? Catalog the approaches used by these systems:
   - v2 plan: keyword heuristics ("no,", "wrong", "actually", "use X instead")
   - pskoett: trigger-based (command errors, user corrections, capability requests, tool failures): https://raw.githubusercontent.com/pskoett/pskoett-ai-skills/main/skills/self-improvement/SKILL.md
   - agent-playbook: hook-based on skill completion, with pattern extraction: https://raw.githubusercontent.com/zhaono1/agent-playbook/main/skills/self-improving-agent/SKILL.md
   - claude-mem: observation capture on every tool use: https://github.com/thedotmack/claude-mem

   Map these on a spectrum from "cheap but noisy" (regex patterns) to "accurate but expensive" (LLM classification). Where should v3 sit given the zero-overhead constraint? Could we do cheap capture + smart filtering at /reflect time?

2. **Signal types taxonomy**: What categories of signals exist beyond the v2 plan's corrections/failures/conventions? Think about:
   - Successful patterns (things that worked well and should be repeated)
   - Time sinks (tasks that took many turns when they shouldn't have)
   - Missing context (Claude had to ask or guess about something that should be documented)
   - Tool preference signals (user prefers one approach over another)
   - Project structure friction (Claude struggled to find files, understand naming)

3. **Capture lifecycle**: Map every Claude Code hook event (PreToolUse, PostToolUse, PostToolUseFailure, PreCompact, SessionStart, Stop, etc.) to what signals could be captured there. Which are worth it? Which are too noisy? What's the cost/benefit?

4. **False positive management**: Every system has a noise problem. How do the references handle it? What's the cost of a false positive vs. a false negative in this context?

Also search the web for "AI agent self-improvement detection" and "LLM session learning extraction" for additional approaches.

Write your findings to docs/research/signal-capture.md with:
- Taxonomy of signal types with examples
- Recognition strategy comparison (table)
- Recommended capture approach for v3
- Hook event mapping with cost/benefit
- Open questions
```

### Agent 3: `project-improver`
**Type**: `general-purpose`
**Focus**: Design question #4 (project-side improvements)

**Prompt**:
```
You are researching how a self-improvement system can propose improvements to the PROJECT ITSELF, not just to Claude's configuration. This is the novel part of the v3 design — most existing systems only improve the agent, but sometimes the project structure is what's holding the agent back.

Read the project document at docs/plans/self-improvement-system-v3.md for full context.

Research these specific questions:

1. **What project-side improvements help agent performance?** Think about:
   - File/folder structure: inconsistent or confusing directory layout
   - Naming: files, functions, variables that don't match their purpose
   - Missing documentation: README gaps, undocumented conventions, missing API docs
   - Code organization: related code spread across unrelated directories
   - Configuration: missing or outdated config files, build scripts
   - Test structure: tests not co-located with code, missing test utilities

   For each, how would Claude detect the problem during normal work, and what would the improvement proposal look like?

2. **Detection approaches**: How can the system detect project-side issues without consuming active session context? Options to research:
   - Post-session analysis: /reflect scans what Claude struggled with and correlates it to project structure
   - Friction signals: When Claude needs many turns to find a file, or makes wrong assumptions about where code lives
   - Cross-session patterns: The same confusion happening in multiple sessions points to a structural issue
   - Static analysis: A separate skill that scans project structure and proposes improvements (like a linter but for project organization)

3. **Proposal format**: How should project-side improvements be presented? They're fundamentally different from "add a line to CLAUDE.md" — they might involve renaming files, moving directories, adding documentation. What level of detail? How to distinguish quick wins from large refactors?

4. **Prior art**: Search the web for "AI code agent project structure analysis", "codebase organization linting", "developer experience static analysis" and similar terms. Are there existing tools or approaches for evaluating project structure from an agent's perspective?

Also look at how beads (https://github.com/steveyegge/beads) handles project-level task tracking and whether its graph structure could represent project improvement proposals.

Write your findings to docs/research/project-improvements.md with:
- Catalog of project-side improvement types with detection strategies
- Recommended approach for v3 (what to include vs. defer)
- Proposal format design
- Open questions
```

### Agent 4: `approach-synthesizer`
**Type**: `general-purpose`
**Focus**: Design question #7 (scope boundaries) + cross-cutting synthesis

**Prompt**:
```
You are the synthesis researcher for a Claude Code self-improvement system redesign. Your job is to deeply analyze all reference implementations, compare their architectural choices, and propose a unified design direction for v3.

Read the project document at docs/plans/self-improvement-system-v3.md for full context. Also read:
- The v1 design: docs/plans/self-improvement-system.md
- The v2 plan: docs/plans/self-improvement-system-v2.md
- The current skills: plugins/self-improvement/skills/self-reflect/SKILL.md and plugins/self-improvement/skills/self-reflect-toggle/SKILL.md

Then deeply analyze each reference implementation:

1. **steveyegge/beads** (https://github.com/steveyegge/beads) — Fetch the README and any docs. Focus on: How does it handle memory decay? How does the graph structure enable tracking dependencies between learnings? What's its approach to keeping memory useful without growing unbounded?

2. **thedotmack/claude-mem** (https://github.com/thedotmack/claude-mem) — Fetch the README and any docs. Focus on: The progressive disclosure pattern (index→timeline→detail). The observation model. How it achieves 10x token savings. The worker service architecture — is it over-engineered for our needs or does it solve real problems?

3. **zhaono1/agent-playbook** (https://raw.githubusercontent.com/zhaono1/agent-playbook/main/skills/self-improving-agent/SKILL.md) — Focus on: The 3-memory model (semantic/episodic/working). Confidence scoring. How learnings propagate to skill updates.

4. **pskoett/pskoett-ai-skills** (https://raw.githubusercontent.com/pskoett/pskoett-ai-skills/main/skills/self-improvement/SKILL.md) — Focus on: The knowledge promotion system. Structured entry format. How learnings graduate from raw capture to permanent memory.

Also search the web for any other Claude Code self-improvement or memory systems that have emerged recently (2025-2026).

Then synthesize:

5. **Architecture comparison table**: For each system, document: storage format, capture mechanism, retrieval strategy, improvement scope (agent-only vs project), extensibility, complexity level.

6. **What to steal from each**: The best idea(s) from each reference that v3 should adopt.

7. **Scope boundaries for v3**: Given the goals and constraints, what should v3 include vs. explicitly defer to future versions? Draw the line clearly. Consider what's the minimum viable system that's still genuinely useful and extensible.

8. **Risks and anti-patterns**: What mistakes have these systems made or what pitfalls should v3 avoid?

Write your findings to docs/research/synthesis.md with:
- Architecture comparison table
- "Steal this" list per reference
- Recommended v3 scope boundary
- Anti-patterns to avoid
- Proposed high-level architecture sketch for v3
```
