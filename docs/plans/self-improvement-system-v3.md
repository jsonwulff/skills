# Self-Improvement System v3: Memory-Driven Agent Learning

## Vision

A memory system for Claude Code that learns from past sessions and proposes improvements — to both Claude's own configuration (CLAUDE.md, hooks, skills) and to the project itself (structure, naming, patterns) — without consuming context or interrupting active work.

## Problem Statement

The current self-improvement system (v1) embeds 38 lines of passive detection instructions into `~/.claude/CLAUDE.md`. In practice this:

- Consumes context in every session regardless of whether learning occurs
- Interrupts focused work with mid-task proposals
- Produces low-quality proposals (Claude forgets instructions mid-task)
- Only considers Claude-side improvements, missing project-side improvements that would also help agent performance

The v2 plan (hook-driven signals + `/reflect`) solves the context/interruption problems but is still scoped narrowly to CLAUDE.md entries.

## Goals

1. **Zero active-session overhead** — No context consumed, no interruptions during work. All learning happens outside the active workflow.
2. **Memory, not instructions** — Replace in-context instructions with a persistent memory layer that captures signals automatically and surfaces them on demand.
3. **Dual-scope improvements** — Not just "teach Claude" but also "improve the project":
   - **Agent-side**: CLAUDE.md entries, hooks, new skills, tool preferences
   - **Project-side**: File/folder structure, naming conventions, code organization, documentation gaps — things that confuse Claude and would confuse any new contributor
4. **Simple start, extensible foundation** — v3 ships as a skill + lightweight storage. The memory format and signal capture should be designed so a future observability dashboard, project management layer, or cross-project analytics system can build on top without migration.
5. **User-controlled** — All improvements proposed, never auto-applied. Easy to enable/disable. Transparent about what was captured and why.

## Constraints

- **No external services** — File-based storage only (JSONL, SQLite at most). No servers, no background daemons.
- **Native-first, extensible later** — Initial implementation uses Python 3 (system) and bash for hooks. The architecture should not preclude adding external packages (e.g. vector DB, semantic search, richer analytics) as optional extensions in the future. Design for a clean boundary where native can be swapped for richer tooling.
- **Works offline** — Everything local to `~/.claude/` and the project directory.
- **Hooks API only** — Use Claude Code's hook system (PreCompact, PostToolUse, SessionStart, SessionEnd, etc.) for signal capture. No monkey-patching.
- **Toggleable** — The entire system (signal capture, memory, hooks) must be cleanly togglable on/off. When off, zero footprint — no hooks running, no context injected, no background processing. A single command or skill invocation should flip the state.

## Key Design Questions for Research

1. **Learning recognition**: How do we identify that something is a learning moment? The v2 plan uses keyword heuristics ("no,", "wrong", "actually") but this is crude. How do other systems detect corrections, discoveries, conventions, and gotchas? Is there a spectrum from cheap pattern matching to LLM-based classification, and where on that spectrum should we sit given the zero-overhead constraint? What signals reliably indicate a learning vs. noise?
2. **Memory architecture**: Flat JSONL append log vs. structured files (`.learnings/`) vs. SQLite? What's the simplest format that supports future querying/analytics?
3. **Signal capture points**: What lifecycle events are worth hooking into? The v2 plan has tool failures, pre-compaction, and post-compaction — what else? Session end summaries? Successful patterns? User prompt analysis?
4. **Project-side improvements**: How do we detect and propose structural improvements (bad naming, confusing file layout, missing docs)? Is this a separate analysis pass or integrated with session reflection?
5. **Cross-session learning**: How do patterns accumulate across sessions? Confidence scoring? Deduplication across sessions?
6. **Retrieval**: When `/reflect` (or a future tool) runs, how does it query memory efficiently? Full scan vs. index vs. search?
7. **Scope boundaries**: What belongs in this system vs. what belongs in a separate project management / observability tool? Where do we draw the line for v3?

## References

### Current State
- **v1 system**: `plugins/self-improvement/` — CLAUDE.md passive detection + `/reflect` batch review
- **v2 plan**: `docs/plans/self-improvement-system-v2.md` — Hook-driven signal capture, zero context overhead

### External References
- **[steveyegge/beads](https://github.com/steveyegge/beads)** — Git-backed graph issue tracker as persistent memory for AI agents. Key ideas: structured task graphs in version control, semantic memory decay, agent-first CLI interface.
- **[thedotmack/claude-mem](https://github.com/thedotmack/claude-mem)** — Full memory system with SQLite + hooks + worker service. Key ideas: progressive disclosure (index → timeline → detail), observation-based capture, 10x token savings through filtered retrieval.
- **[zhaono1/agent-playbook self-improving-agent](https://github.com/zhaono1/agent-playbook/tree/main/skills/self-improving-agent)** — Multi-memory system (semantic patterns, episodic experiences, working context). Key ideas: confidence scoring, automatic skill updates, experience extraction from all skill executions.
- **[pskoett/pskoett-ai-skills self-improvement](https://github.com/pskoett/pskoett-ai-skills/tree/main/skills/self-improvement)** — Structured `.learnings/` directory with LEARNINGS.md, ERRORS.md, FEATURE_REQUESTS.md. Key ideas: knowledge promotion system (learnings graduate to CLAUDE.md), structured entry format with IDs/priority/status, skill extraction from recurring patterns.

## File Structure (Current)

```
~/Development/skills/
  plugins/
    self-improvement/
      .claude-plugin/plugin.json
      skills/
        self-reflect/SKILL.md        # End-of-session batch reflection
        self-reflect-toggle/SKILL.md # Toggle passive detection on/off
  docs/plans/
    self-improvement-system.md       # v1 design
    self-improvement-system-v2.md    # v2 hook-driven design
    self-improvement-system-v3.md    # This document
```
