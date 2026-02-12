# Reference Implementation Synthesis for Self-Improvement System v3

## 1. Architecture Comparison Table

| Dimension | steveyegge/beads | thedotmack/claude-mem | zhaono1/agent-playbook | pskoett/pskoett-ai-skills | achillesheel02/claude-self-improve | rlancemartin/claude-diary | Native Auto Memory |
|---|---|---|---|---|---|---|---|
| **Storage format** | SQLite + JSONL (dual-layer, git-tracked JSONL as source of truth) | SQLite (FTS5) + Chroma vector DB | JSON files per memory type (`memory/semantic-patterns.json`, `memory/episodic/YYYY-MM-DD-{skill}.json`) | Markdown files in `.learnings/` directory (LEARNINGS.md, ERRORS.md, FEATURE_REQUESTS.md) | MEMORY.md + `metrics.jsonl` + `analysis.json` + topic files | Markdown diary files in `~/.claude/memory/diary/YYYY-MM-DD-session-N.md` | Markdown files in `~/.claude/projects/<project>/memory/` (MEMORY.md index + topic files) |
| **Capture mechanism** | CLI commands (`bd create`, `bd update`); agent-driven explicit capture | 6 lifecycle hooks (SessionStart, UserPromptSubmit, PostToolUse, Stop, SessionEnd, Pre-install) | Hooks (`before_start`, `after_complete`, `on_error`); manual triggers ("self-improve", "analyze today's experience") | Automatic triggers on command failures, user corrections ("Actually..."), missing capabilities, API failures | 4-stage pipeline: auto-generate facets from transcripts (Claude Haiku), collect, analyze (Claude Sonnet), update | PreCompact hook triggers diary entry generation | Claude writes to memory files during session; user can request saves ("remember that we use pnpm") |
| **Retrieval strategy** | CLI queries (`bd ready`, `bd show`); SQLite indexes; blocked-issues cache for O(1) ready-task lookups | Progressive disclosure: index (~50-100 tokens) -> timeline -> detail (~500-1000 tokens per result); hybrid semantic + keyword search | Direct file reads; working memory loaded at session start; semantic patterns queried by category/confidence | Manual review; status-based filtering (pending/in_progress/resolved/promoted); priority/area tags | MEMORY.md loaded at session start; topic files read on demand | Diary entries read during `/reflect`; `processed.log` tracks what has been analyzed | MEMORY.md first 200 lines loaded into system prompt; topic files read on demand |
| **Improvement scope** | Project task management (agent workflow, not self-improvement per se) | Agent-side only (observations about Claude's actions) | Agent-side (skill updates, pattern refinement, confidence scoring) | Dual: agent-side (CLAUDE.md) + project-side (AGENTS.md, .github/copilot-instructions.md, SOUL.md, TOOLS.md) | Agent-side (MEMORY.md updates, anti-patterns, friction tracking) | Agent-side (CLAUDE.md rules, preference documentation) | Agent-side (project patterns, debugging insights, architecture notes, preferences) |
| **Extensibility** | High: Dolt backend, plugin system, daemon mode, multi-repo sync | High: MCP server, REST API, web viewer, worker service | Medium: JSON schema allows new memory types; skill file updates are structured | Medium: new promotion targets can be added; skill extraction pipeline | Medium: facet schema extensible; topic files for overflow | Low: simple markdown files, no structured query | Medium: topic files extensible; `.claude/rules/` for modular organization |
| **Complexity level** | Very High: Dolt DB, Go daemon, goroutine flush manager, multi-repo hydration | Very High: Bun worker service, Chroma vector DB, SQLite, MCP server, 10 search endpoints | Medium: JSON files, hook scripts, no external services | Low-Medium: plain markdown, shell scripts, structured IDs | Medium: headless Claude API calls for analysis, JSONL metrics | Low: shell hook + markdown files | Low: native feature, markdown files, no configuration needed |

## 2. "Steal This" -- Best Ideas From Each Reference

### From steveyegge/beads

1. **Ephemeral wisps pattern**: The distinction between permanent records and ephemeral work items (wisps) that never leave the local database is directly applicable. Raw signal captures should be ephemeral by default -- only "squashed" into permanent learnings after analysis. This naturally prevents unbounded growth.

2. **Content-based hashing for deduplication**: Using hash-derived identifiers instead of sequential IDs prevents merge collisions and enables robust deduplication across sessions. v3 could hash learning content to detect duplicates without expensive string comparison.

3. **Blocked-issues cache / materialized views**: The idea of pre-computing derived state (e.g., "which learnings are ready for promotion") and caching it for fast retrieval. If v3 ever needs to query learnings efficiently, materialized indexes are the pattern.

### From thedotmack/claude-mem

4. **Progressive disclosure (index -> timeline -> detail)**: This is the single most important pattern for token efficiency. v3 should never dump full learning history into context. Instead: load a compact index (categories + counts), let the agent drill into specific areas on demand, and only surface full details for selected items.

5. **Observation model**: Capturing discrete "observations" rather than free-form notes gives structure without rigidity. Each observation has a type, timestamp, and content -- simple enough to append, structured enough to query.

6. **Hybrid search (semantic + keyword)**: While too complex for v3 initial scope, the architecture should not preclude adding vector search later. Designing entries with both natural language content and categorical tags enables future hybrid retrieval.

### From zhaono1/agent-playbook

7. **Three-memory model (semantic / episodic / working)**: The separation of abstract patterns (semantic) from concrete experiences (episodic) from current-session state (working) is psychologically sound and practically useful. v3 should adopt a simplified version: permanent patterns (promoted learnings) vs. session episodes (raw captures) vs. working context (current session signals).

8. **Confidence scoring with decay**: Patterns gain confidence through successful application and user feedback, and lose it through disuse. This prevents stale learnings from polluting the knowledge base. v3 should track at minimum: times-applied count, last-applied timestamp, and user feedback signal.

9. **Experience-to-pattern abstraction pipeline**: The four-phase loop (extract -> abstract -> update skills -> consolidate memory) provides a clean model for how raw captures become permanent improvements. v3's `/reflect` should follow this: gather raw signals, abstract patterns, propose skill/CLAUDE.md updates, clean up.

### From pskoett/pskoett-ai-skills

10. **Knowledge promotion system with explicit status lifecycle**: The `pending -> in_progress -> resolved -> promoted` status progression is the clearest model for learning maturation. Every raw capture starts as pending; analysis moves it to resolved; if broadly applicable, it gets promoted to CLAUDE.md or a skill. This is the core workflow v3 should adopt.

11. **Structured entry format with IDs and metadata**: The `LRN-YYYYMMDD-XXX` ID scheme with priority, status, and area tags makes entries queryable and trackable without a database. JSONL entries in v3 should include: ID, timestamp, type, status, priority, source, and content.

12. **Promotion criteria as explicit rules**: "Applies across multiple files/features" and "any contributor should know" are clear, actionable criteria for when a learning graduates from raw capture to permanent memory. v3 should encode similar criteria in the `/reflect` skill instructions.

13. **Skill extraction from recurring patterns**: When the same learning recurs 3+ times, it should be extractable as a new skill. This is the ultimate graduation path: raw signal -> learning -> CLAUDE.md entry -> dedicated skill.

### From achillesheel02/claude-self-improve

14. **Headless Claude for cross-session analysis**: Using a separate Claude invocation (cheap model like Haiku) to analyze accumulated session facets is clever. It enables pattern detection across sessions without consuming the active session's context. However, this adds cost and complexity that v3 should defer.

15. **Six analytical dimensions**: The friction/success/anti-pattern/preference/domain/trend framework provides comprehensive session analysis categories. v3's `/reflect` should consider at least friction patterns, success patterns, and domain lessons alongside the existing categories.

16. **Timestamped backups before memory updates**: Always backing up MEMORY.md before writing changes is a simple safety measure v3 should adopt.

### From rlancemartin/claude-diary

17. **PreCompact hook as primary capture point**: Using the PreCompact hook (before context compaction) to generate diary entries is the most natural capture point -- it's when context is about to be lost, making it the ideal moment to extract learnings. This aligns perfectly with v2's architecture and should remain central to v3.

18. **Processed.log for tracking analyzed entries**: A simple log of which entries have been analyzed prevents duplicate processing during reflection. Cheaper than marking each entry individually.

19. **Structured diary sections**: Task summary, design decisions, user preferences, challenges, solutions, code patterns -- these categories provide a template for what to extract during capture.

### From Native Auto Memory

20. **MEMORY.md as concise index with topic file overflow**: The pattern of keeping a brief index (first 200 lines loaded automatically) with detailed topic files read on demand is exactly the progressive disclosure pattern applied to file-based storage. v3 should adopt this structure rather than a single growing file.

21. **Memory scoped to project via git root**: Using the git repository root to determine memory scope is the right default. All sessions in the same repo share one memory directory.

22. **User-initiated saves**: "Remember that we use pnpm" -- direct user commands to save specific learnings should be supported alongside automatic capture.

## 3. Recommended v3 Scope Boundary

### IN SCOPE for v3

#### Core Memory Architecture
- **JSONL append log** (`~/.claude/reflections/signals.jsonl`) for raw signal capture -- ephemeral, cleaned up after processing
- **Structured learnings directory** (`~/.claude/reflections/learnings/`) with a `LEARNINGS.md` index file + topic files for overflow
- **Status lifecycle**: `captured -> analyzed -> promoted | dismissed` for each learning entry
- **Entry format**: ID (`SIG-YYYYMMDD-XXXX`), timestamp, session_id, type (correction, failure, convention, gotcha, preference, command), status, confidence (0-3 scale: low/medium/high/verified), source (hook/reflect/user), content, context

#### Signal Capture (Hooks)
- **PreCompact hook** (from v2): transcript analysis before compaction, writes to signals.jsonl
- **PostToolUseFailure hook** (from v2): async failure logging to signals.jsonl
- **SessionStart hook** (from v2): post-compaction context injection from signals.jsonl
- **SessionEnd hook** (new): lightweight session summary extraction -- captures the "what happened" before the session closes

#### Reflection & Promotion (`/reflect` skill)
- **Enhanced gather**: reads both conversation + signals.jsonl
- **Pattern detection**: groups similar signals, identifies recurring themes (3+ occurrences = high confidence)
- **Dual-scope proposals**: agent-side (CLAUDE.md, auto memory) AND project-side (naming, structure, documentation gaps)
- **Promotion workflow**: raw signal -> analyzed learning -> proposed CLAUDE.md/skill entry -> user approval -> write
- **Deduplication**: against existing CLAUDE.md content and previously processed signals
- **Cleanup**: mark processed signals, prune signals older than 14 days

#### Toggle System (`/reflect-toggle` skill)
- Toggles all hooks in `~/.claude/settings.json`
- Migration from v1 (remove CLAUDE.md passive section)
- Clean on/off: zero footprint when disabled

#### Compatibility with Native Auto Memory
- v3 should complement, not compete with, Claude's native auto memory
- Auto memory handles in-session saves ("remember X"); v3 handles cross-session pattern analysis and structured improvement proposals
- v3 learnings can promote to auto memory topic files as an alternative to CLAUDE.md

### OUT OF SCOPE for v3 (deferred to future)

| Feature | Rationale for deferring |
|---|---|
| **Vector/semantic search** | Requires external dependencies (Chroma, etc.). File-based grep + categorical tags are sufficient for v3 volume. Design entries with natural language content so vector search can be added later. |
| **Headless Claude for automated analysis** | Adds API cost and complexity. `/reflect` is user-initiated and uses the active session's Claude. Cross-session automated analysis can be added as a separate skill later. |
| **Background worker service** | claude-mem's Bun worker is over-engineered for our needs. Hooks + skill invocation cover the capture/analysis loop without a daemon. |
| **SQLite storage** | JSONL + markdown is sufficient at the expected volume (tens to low hundreds of signals per project). SQLite becomes worthwhile only at scale that v3 will not reach. Design the entry format so migration to SQLite is straightforward. |
| **MCP server integration** | Valuable for cross-tool interop but adds significant complexity. Keep v3 as pure hooks + skills. |
| **Cross-project analytics** | Interesting but requires aggregation infrastructure. v3 scopes learnings per-project (via session_id and project path). |
| **Automated skill extraction** | The full pipeline of "recurring learning -> generated SKILL.md" is ambitious. v3 can flag candidates ("this pattern has recurred 5 times, consider extracting as a skill") but should not auto-generate skill files. |
| **Confidence decay over time** | Useful in theory but adds complexity to a file-based system. v3 tracks confidence as a simple counter (application count + user feedback). Time-based decay can be added later. |
| **Dashboard / web UI** | Nice-to-have visualization but not core. The structured JSONL + markdown format enables future tooling without building it now. |
| **Project-side auto-detection** | Automatically detecting bad naming, confusing structure, etc. requires deep project analysis. v3 should capture project-side observations when they surface during normal work (e.g., Claude gets confused by a file layout) but not proactively scan for issues. |

### The Scope Line

v3 is a **memory-backed reflection system**: it captures signals automatically via hooks, stores them in structured but simple file formats, and surfaces them through an enhanced `/reflect` skill that proposes dual-scope improvements. It does NOT run background services, make API calls, use databases, or auto-apply changes.

The minimum viable system is: hooks that capture signals + a reflection skill that reads them and proposes improvements + a toggle to turn it on/off. Everything else is enhancement.

## 4. Anti-Patterns to Avoid

### From the reference implementations

1. **The "capture everything" trap** (claude-mem)
   claude-mem hooks into 6 lifecycle events and captures every tool use as an observation. This produces enormous volumes of data, most of which is noise. The 10x token savings from progressive disclosure is a bandage for a capture problem.
   **v3 should**: Capture selectively. Hook into high-signal events (PreCompact, tool failures, session end) rather than every action. Accept false negatives -- `/reflect` independently scans the conversation to catch what hooks missed.

2. **Over-engineering the storage layer** (beads, claude-mem)
   Beads uses Dolt + SQLite + JSONL with a Go daemon, flush manager, and goroutine coordination. claude-mem uses SQLite + Chroma + Bun worker service + MCP server. This complexity is justified for their goals but lethal for a system that needs to "just work" as a Claude Code skill.
   **v3 should**: Use the simplest storage that works (JSONL + markdown). Design entries so they can migrate to SQLite later, but do not use SQLite now.

3. **Unbounded memory accumulation** (pskoett, agent-playbook without cleanup)
   Both pskoett and agent-playbook append learnings but have weak cleanup mechanisms. Over time, the learnings directory or JSON files grow without bound, eventually consuming context or becoming impossible to navigate.
   **v3 should**: Implement explicit lifecycle management. Signals have a 14-day TTL. Promoted learnings move out of the signals file into CLAUDE.md/skills. The signals file is the temporary staging area, not the permanent store.

4. **Confidence without calibration** (agent-playbook)
   agent-playbook's confidence scoring (0.0-1.0 floating point) suggests false precision. In practice, distinguishing confidence 0.6 from 0.7 is meaningless.
   **v3 should**: Use a coarse confidence scale (low/medium/high/verified) based on concrete signals: low = single occurrence, medium = 2 occurrences, high = 3+ occurrences, verified = user-confirmed.

5. **Auto-applying changes** (agent-playbook skill updates, claude-self-improve MEMORY.md writes)
   Both agent-playbook and claude-self-improve automatically modify skill files and MEMORY.md without user approval. This violates the user-controlled constraint and can introduce incorrect or unwanted changes.
   **v3 should**: Always propose, never auto-apply. Every change goes through user approval via `/reflect`.

6. **Competing with native features** (all external memory plugins vs. auto memory)
   Claude Code now has native auto memory (`~/.claude/projects/<project>/memory/`). Any plugin that reimplements this will be fighting the platform.
   **v3 should**: Complement auto memory, not replace it. Auto memory handles in-session saves; v3 handles cross-session pattern analysis and structured improvement proposals. v3 can promote learnings INTO auto memory topic files.

7. **Monolithic memory files** (claude-self-improve MEMORY.md, early CLAUDE.md approaches)
   A single growing file eventually exceeds useful context size. Native auto memory already limits MEMORY.md to 200 lines.
   **v3 should**: Follow the index + topic file pattern. Keep the main index lean; overflow details into topic files that are read on demand.

8. **Interrupting the user's workflow** (v1 passive CLAUDE.md approach, claude-self-improve during-session analysis)
   The primary complaint about v1 is that it interrupts focused work. Any capture that requires user interaction during normal work is a failure.
   **v3 should**: Capture silently via hooks. Analysis happens only when the user explicitly invokes `/reflect`. Zero interruptions, zero context overhead during normal work.

### General anti-patterns from Addy Osmani's analysis

9. **Memory accumulation without reset**: Agents that carry forward growing context confuse prior iterations with current work. v3's ephemeral signals file (cleaned after `/reflect`) prevents this.

10. **Absent validation**: Learnings proposed without evidence are low-quality. v3 should include the source context (the actual user correction, the actual error message) in each learning entry so `/reflect` can validate before proposing.

11. **Ignored context bloat**: Growing prompt sizes dilute model attention. v3's progressive disclosure (index file + on-demand topic files) directly addresses this.

## 5. Proposed High-Level Architecture for v3

```
                         CAPTURE LAYER (hooks, silent, zero context)
                         ============================================
 ┌─────────────────┐    ┌──────────────────┐    ┌──────────────────┐
 │  PreCompact      │    │ PostToolUse      │    │ SessionEnd       │
 │  hook            │    │ Failure hook     │    │ hook             │
 │                  │    │ (async)          │    │                  │
 │  Reads transcript│    │ Logs tool name,  │    │ Extracts session │
 │  before compact, │    │ error excerpt,   │    │ summary: what    │
 │  extracts:       │    │ command to       │    │ was accomplished,│
 │  - corrections   │    │ signals.jsonl    │    │ key decisions,   │
 │  - conventions   │    │                  │    │ unresolved issues│
 │  - repeated fails│    │                  │    │ to signals.jsonl │
 │  - discoveries   │    │                  │    │                  │
 │  to signals.jsonl│    │                  │    │                  │
 └────────┬─────────┘    └────────┬─────────┘    └────────┬─────────┘
          │                       │                       │
          ▼                       ▼                       ▼
 ┌────────────────────────────────────────────────────────────────────┐
 │                    ~/.claude/reflections/signals.jsonl              │
 │                                                                    │
 │  Append-only JSONL. Each entry:                                    │
 │  {                                                                 │
 │    "id": "SIG-20260211-0001",                                      │
 │    "ts": "2026-02-11T10:23:00Z",                                   │
 │    "sid": "abc123",          // session ID                         │
 │    "type": "correction",     // correction|failure|convention|     │
 │                              // gotcha|preference|command|summary  │
 │    "status": "captured",     // captured|analyzed|promoted|dismissed│
 │    "confidence": 1,          // 1=low, 2=medium, 3=high, 4=verified│
 │    "source": "hook",         // hook|reflect|user                  │
 │    "content": "Use pnpm, not npm in this project",                 │
 │    "context": "User said: 'No, use pnpm not npm'"                 │
 │  }                                                                 │
 │                                                                    │
 │  TTL: 14 days. Cleaned by /reflect and by capture-signals.py.     │
 └──────────────────────────────────┬─────────────────────────────────┘
                                    │
          CONTEXT INJECTION         │
          (post-compaction only)    │
 ┌──────────────────────────────────┴─────────────────────────────────┐
 │  SessionStart hook (matcher: "compact")                            │
 │  Reads signals.jsonl for current session, injects compact summary  │
 │  as additionalContext so signals survive compaction.                │
 └────────────────────────────────────────────────────────────────────┘
                                    │
          ANALYSIS LAYER            │
          (/reflect skill,          │
           user-initiated)          │
 ┌──────────────────────────────────┴─────────────────────────────────┐
 │                         /reflect                                   │
 │                                                                    │
 │  1. GATHER                                                         │
 │     - Read signals.jsonl (captured entries)                        │
 │     - Scan current conversation                                    │
 │     - Merge, deduplicate                                          │
 │                                                                    │
 │  2. ANALYZE                                                        │
 │     - Group by type                                                │
 │     - Detect patterns (same signal 3+ times = high confidence)     │
 │     - Classify scope (global vs project)                           │
 │     - Classify improvement type:                                   │
 │       - Agent-side: CLAUDE.md entry, auto memory, hook, skill     │
 │       - Project-side: naming, structure, documentation, patterns   │
 │                                                                    │
 │  3. PROPOSE                                                        │
 │     - Present grouped proposals with evidence                      │
 │     - User approves/picks/skips per batch                         │
 │                                                                    │
 │  4. WRITE                                                          │
 │     - Approved entries -> target file (CLAUDE.md, auto memory,    │
 │       project CLAUDE.md, etc.)                                     │
 │     - Back up target file before writing                           │
 │                                                                    │
 │  5. CLEAN UP                                                       │
 │     - Mark processed signals as analyzed/promoted/dismissed        │
 │     - Prune signals older than 14 days                            │
 │     - Update learnings index if using topic files                  │
 └────────────────────────────────────────────────────────────────────┘
                                    │
          STORAGE LAYER             │
          (permanent learnings)     │
 ┌──────────────────────────────────┴─────────────────────────────────┐
 │                                                                    │
 │  Promotion targets (user-approved destinations):                   │
 │                                                                    │
 │  ~/.claude/CLAUDE.md            - Global agent preferences         │
 │  <project>/CLAUDE.md            - Project-specific conventions     │
 │  <project>/.claude/CLAUDE.md    - Project-specific conventions     │
 │  ~/.claude/projects/<p>/memory/ - Auto memory topic files          │
 │  <project>/.claude/rules/*.md   - Modular project rules           │
 │                                                                    │
 │  Future promotion targets (out of scope for v3):                   │
 │  - New skill files (SKILL.md)                                     │
 │  - New hook scripts                                                │
 │  - Project structural changes                                      │
 └────────────────────────────────────────────────────────────────────┘
                                    │
          TOGGLE LAYER              │
 ┌──────────────────────────────────┴─────────────────────────────────┐
 │  /reflect-toggle                                                   │
 │                                                                    │
 │  ON:  Adds PreCompact, PostToolUseFailure, SessionEnd,            │
 │       SessionStart(compact) hooks to ~/.claude/settings.json       │
 │       Removes old CLAUDE.md passive section if present             │
 │                                                                    │
 │  OFF: Removes all self-improvement hooks from settings.json        │
 │       Zero footprint when disabled                                 │
 └────────────────────────────────────────────────────────────────────┘
```

### Key Architecture Decisions

| Decision | Rationale | Reference inspiration |
|---|---|---|
| **JSONL signals file as ephemeral staging area** | Raw captures are temporary; only promoted learnings persist. Prevents unbounded growth. | beads (wisps), pskoett (status lifecycle) |
| **Progressive disclosure: lean index + topic files** | Prevents context bloat. Load minimum, drill down on demand. | claude-mem (index->timeline->detail), native auto memory (200-line MEMORY.md) |
| **Coarse confidence scale (1-4)** | Avoids false precision. Based on concrete signals: occurrence count + user feedback. | agent-playbook (confidence scoring), simplified |
| **Status lifecycle for entries** | Makes the journey from capture to promotion explicit and trackable. | pskoett (pending->resolved->promoted) |
| **Dual-scope proposals** | Addresses both "teach Claude" and "improve the project" in one system. | pskoett (multiple promotion targets), v3 goals |
| **Complement native auto memory** | Does not compete with platform features. Uses auto memory as a promotion target. | Avoiding the anti-pattern of fighting the platform |
| **No external services or API calls** | Stays within the "no servers, no daemons, works offline" constraint. Hook scripts + skill invocation only. | Avoiding claude-mem/beads complexity |
| **SessionEnd hook (new vs v2)** | Session end is a natural boundary for extracting "what happened" summaries. PreCompact alone misses sessions that end without compaction. | claude-diary (session-based capture), claude-self-improve (session facets) |
| **14-day TTL on signals** | Generous enough to accumulate cross-session patterns; short enough to prevent unbounded growth. | v2 (7 days), extended for cross-session value |
| **User approval for all writes** | Non-negotiable constraint from v3 goals. Avoids the auto-apply anti-pattern. | v3 constraints, avoiding agent-playbook's auto-updates |

### File Structure

```
~/Development/skills/plugins/self-improvement/
  .claude-plugin/plugin.json
  skills/
    self-reflect/
      SKILL.md                          # Enhanced: signals + dual-scope + cleanup
      hooks/
        capture-signals.py              # PreCompact: transcript parser
        inject-signals.sh              # SessionStart(compact): context injector
        capture-failure.sh             # PostToolUseFailure: failure logger
        capture-session-summary.py     # SessionEnd: session summary extractor
    self-reflect-toggle/
      SKILL.md                          # Toggles hooks in settings.json

Runtime data:
~/.claude/reflections/
  signals.jsonl                         # Ephemeral signal staging area (14-day TTL)
```

### How v3 Differs From v2

| Aspect | v2 | v3 |
|---|---|---|
| Scope | Agent-side only (CLAUDE.md entries) | Dual-scope: agent-side + project-side |
| Memory model | Flat signal log, no lifecycle | Ephemeral signals -> analyzed learnings -> promoted entries |
| Confidence | None | Coarse 4-level scale based on occurrence count |
| Session boundary capture | PreCompact only | PreCompact + SessionEnd |
| Promotion targets | CLAUDE.md (global + project) | CLAUDE.md + auto memory + .claude/rules/ + project docs |
| Compatibility with native features | Pre-dates auto memory | Explicitly complements auto memory |
| Cleanup | 7-day prune | 14-day TTL + status lifecycle (promoted/dismissed entries cleaned) |
| Project-side improvements | Not addressed | Captured as observations, proposed during /reflect |
| Signal entry format | Minimal (ts, sid, type, context, turn) | Full metadata (id, ts, sid, type, status, confidence, source, content, context) |

### Migration Path From v1/v2

1. `/reflect-toggle` detects and removes the old CLAUDE.md passive section (v1 migration)
2. If v2 hooks exist, `/reflect-toggle` updates them to v3 hook scripts (v2 migration)
3. If `~/.claude/reflections/signals.jsonl` exists with v2-format entries (no `status` or `confidence` fields), the v3 capture scripts treat them as `status: captured, confidence: 1` (backwards compatible)
4. No data loss in any migration path

---

*Research conducted 2026-02-11. Sources: steveyegge/beads, thedotmack/claude-mem, zhaono1/agent-playbook, pskoett/pskoett-ai-skills, achillesheel02/claude-self-improve, rlancemartin/claude-diary, Claude Code native auto memory documentation, Addy Osmani's "Self-Improving Coding Agents".*
