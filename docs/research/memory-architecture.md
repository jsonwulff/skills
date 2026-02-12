# Memory Architecture Research: Storage, Retrieval, and Cross-Session Learning

Research for the v3 Self-Improvement System. Addresses Key Design Questions #2, #5, and #6 from `docs/plans/self-improvement-system-v3.md`.

## 1. Reference Implementation Analysis

### 1.1 claude-mem (thedotmack)

**Storage**: SQLite + FTS5 full-text search, with optional Chroma vector database for semantic search.

**Architecture**: MCP server with 5 tools (search, timeline, get_observations, save_memory, workflow docs). Uses 5 lifecycle hooks (SessionStart, UserPromptSubmit, PostToolUse, Stop, SessionEnd) to capture observations automatically.

**Retrieval**: Progressive disclosure in 3 layers:
1. **Search layer** (~50-100 tokens): Returns compact index with observation IDs via full-text and semantic matching
2. **Timeline layer** (variable): Provides chronological context around specific results
3. **Detail layer** (~500-1000 tokens): Fetches complete observation data only for filtered IDs

Claims ~10x token savings by filtering before retrieving full content.

**Key insight**: The 3-layer retrieval is the most sophisticated approach in the reference set. It separates _finding_ relevant memories from _loading_ them, which maps well to the constraint of zero active-session overhead.

**Limitation**: Requires an MCP server process, Chroma dependency for vector search. Heavy for a skill-only system.

### 1.2 pskoett (structured markdown files)

**Storage**: `.learnings/` directory with three markdown files:
- `LEARNINGS.md` -- Insights, corrections, best practices
- `ERRORS.md` -- Command failures, unexpected behaviors
- `FEATURE_REQUESTS.md` -- Requested capabilities

**Entry format**: Unique IDs (`TYPE-YYYYMMDD-XXX`), metadata (timestamp, priority, status, area tags), summary, context, suggested actions, and cross-references ("See Also" links).

**Knowledge promotion**: High-value learnings graduate from `.learnings/` to permanent targets (CLAUDE.md, AGENTS.md, etc.). Original entry status changes to "promoted."

**Skill extraction**: Entries with 2+ cross-references, resolved status, and broad applicability become candidate skills.

**Key insight**: The promotion pipeline (raw learning -> structured entry -> promoted to CLAUDE.md -> extracted as skill) is the most mature lifecycle model. The structured markdown format is human-readable and git-friendly.

**Limitation**: No indexing. Retrieval is full-file scan. The three separate files create an implicit categorization burden at write time.

### 1.3 agent-playbook (zhaono1)

**Storage**: JSON files organized by memory type:
- `memory/semantic-patterns.json` -- Abstract reusable patterns with confidence scores
- `memory/episodic/YYYY-MM-DD-{skill}.json` -- Specific dated experiences
- `memory/working/current_session.json` -- Active session state

**Confidence scoring**: Patterns track application count and source (user feedback, implementation review, retrospective). Rule: 3+ repetitions elevate to "critical" confidence. Low-confidence patterns with no recent applications are pruned during consolidation.

**Deduplication**: Implicit through abstraction -- concrete experiences are generalized into semantic patterns, preventing duplicates at the pattern level.

**Lifecycle hooks**: `before_start` (session logging), `after_complete` (pattern extraction + skill modification), `on_error` (error capture).

**Key insight**: The semantic/episodic/working memory split maps cleanly to different retrieval needs: semantic for "what do I know", episodic for "what happened", working for "what am I doing now." Confidence scoring provides a natural pruning mechanism.

**Limitation**: JSON files become unwieldy as patterns accumulate. No search beyond loading the full file.

### 1.4 beads (steveyegge)

**Storage**: Dolt (version-controlled SQL database) + JSONL for git portability. Hash-based task IDs (`bd-a1b2`) prevent merge conflicts across agents/branches.

**Memory decay**: Older closed tasks are summarized rather than retained verbatim, conserving context window during extended sessions.

**Key insight**: Dolt's cell-level merge is elegant for multi-agent collaboration. The hash-based ID scheme avoids the classic problem of sequential IDs colliding across concurrent sessions. The dual Dolt+JSONL approach lets you query fast locally while keeping git compatibility.

**Limitation**: Dolt is a heavy dependency. The task-graph model is designed for issue tracking, not general learning signals.

### 1.5 Claude Code Auto Memory (official, built-in)

**Storage**: Markdown files in `~/.claude/projects/<project>/memory/`:
- `MEMORY.md` -- Concise index, first 200 lines loaded into every session
- Topic files (`debugging.md`, `api-conventions.md`, etc.) -- Detailed notes, loaded on demand

**Retrieval**: `MEMORY.md` acts as an index. Claude reads topic files on demand using standard file tools. No search infrastructure.

**Key insight**: This is already shipping and establishes the baseline. The 200-line limit on MEMORY.md creates a natural pressure toward conciseness. Topic files provide overflow. The on-demand loading pattern (index loaded, details fetched when needed) is a simpler version of claude-mem's progressive disclosure.

**Limitation**: No structured format. No confidence scoring. No promotion or lifecycle. No queryability beyond "Claude reads the file." Our v3 system should complement this, not replace it.

## 2. Storage Format Comparison

| Criterion | JSONL Append Log | Structured Markdown (.learnings/) | SQLite (+FTS5) | Hybrid: JSONL + Markdown Index |
|---|---|---|---|---|
| **Simplicity** | Excellent. Append-only, one line per entry. Trivially written from bash/python hooks. | Good. Human-readable, familiar format. Requires parsing for programmatic access. | Moderate. Requires schema design, migration story. Python's `sqlite3` is stdlib though. | Good. JSONL for machine, markdown for human. |
| **Queryability** | Poor. Full scan only. `grep` works for simple filters, breaks for complex queries. | Poor. Regex/grep on markdown is fragile. | Excellent. SQL queries, FTS5 for text search. Aggregation, filtering, sorting all native. | Moderate. JSONL can be filtered with `jq`; markdown index provides overview. |
| **Git-friendliness** | Good. Append-only means merge conflicts only occur at the last line. But diffs are noisy for large files. | Excellent. Markdown diffs are clean and human-reviewable. Natural fit for version control. | Poor. Binary file. Must be .gitignored. Changes invisible in diffs. | Good. Both formats diff well. |
| **Concurrent session safety** | Moderate. Append is mostly safe but two concurrent appends can interleave. File locking needed for strict safety. | Poor. Two sessions editing the same markdown file will conflict. | Good. SQLite handles concurrent reads and serialized writes natively (WAL mode). | Moderate. Same JSONL concerns, but markdown index is only written by `/reflect`, not by hooks. |
| **Future extensibility** | Moderate. A dashboard could parse JSONL. Adding fields is backwards-compatible. But no schema enforcement. | Moderate. A dashboard could parse markdown, but it's fragile. Custom parsers needed. | Excellent. Schema evolution via migrations. Any analytics tool can connect. Dashboard reads SQL directly. | Good. JSONL is the machine-readable layer; dashboards consume JSONL. Markdown is the human layer. |
| **Token efficiency** | Good. Each entry is self-contained. Load only what you need by line filtering. | Poor. Must load entire file sections. Markdown formatting adds overhead tokens. | N/A (not loaded directly into context). Query results are formatted for context injection. | Good. Load JSONL entries selectively; markdown index is concise. |
| **Debugging / inspection** | Good. `cat`, `tail`, `jq` all work. | Excellent. Open in any editor, immediately readable. | Moderate. Requires `sqlite3` CLI or DB browser. | Excellent. Both layers are independently inspectable. |

### Analysis

No single format wins across all criteria. The tradeoffs cluster into two camps:

**Human-first** (structured markdown): Best for readability, git diffs, manual inspection. Worst for programmatic querying and concurrent access. pskoett's approach lives here.

**Machine-first** (SQLite): Best for querying, concurrent access, extensibility. Worst for git integration and casual inspection. claude-mem lives here.

**JSONL sits in the middle**: Good enough for both humans and machines, excellent at neither. The v2 plan already chose JSONL for `signals.jsonl` and it works well for the append-only signal capture use case.

The key question is: what does v3 need to query? If `/reflect` is the only consumer and it runs infrequently (end of session), full-file scan of a JSONL log is adequate. If a future dashboard or cross-project analytics needs to query, we need either SQLite or a well-structured JSONL with a consistent schema that a dashboard can parse.

## 3. Cross-Session Accumulation

### 3.1 The Accumulation Problem

Learning signals accumulate across sessions. Without management, the memory store grows unboundedly, becoming noisy (too many low-value entries), stale (entries about deprecated patterns), and duplicative (the same lesson captured 5 times).

### 3.2 Confidence Scoring

agent-playbook's approach: track `application_count` per pattern. Each time a pattern is confirmed (applied successfully, user agrees), increment. Each time it's contradicted, decrement or flag for review.

**Recommended approach for v3**:

Each learning entry gets a `confidence` field with values:
- `signal` (raw, unreviewed) -- Written by hooks automatically
- `candidate` (reviewed by `/reflect`, deemed plausible) -- Written by `/reflect` analysis
- `confirmed` (user-approved or applied 3+ times) -- Written when user approves a `/reflect` proposal
- `promoted` (graduated to CLAUDE.md or became a skill) -- Written when the learning is promoted

This is simpler than a numeric score and maps directly to the lifecycle stages. The v3 system never needs to compute a floating-point confidence -- it just needs to know where in the pipeline an entry sits.

### 3.3 Deduplication Strategies

Three approaches observed in references:

1. **Exact match on context string** (v2 signals.jsonl): Simple but misses semantic duplicates ("use pnpm" vs "don't use npm").
2. **Abstraction-based** (agent-playbook): Concrete experiences are generalized into abstract patterns. Dedup happens at the abstract level. Requires LLM intelligence.
3. **ID + cross-reference** (pskoett): Entries link to related entries. Dedup is manual during review.

**Recommended approach for v3**: Two-tier dedup.
- **Tier 1 (hooks, cheap)**: Exact substring match on the `context` field. If the last 10 entries contain the same core string, skip. Prevents rapid-fire duplicates from repeated tool failures.
- **Tier 2 (/reflect, LLM-powered)**: When `/reflect` reviews signals, it groups semantically similar entries and merges them into a single candidate. This is where "use pnpm" and "don't use npm" become one learning.

### 3.4 Memory Decay and Pruning

References show three decay strategies:

1. **Time-based** (v2 plan): Entries older than 7 days are pruned. Simple but destroys valuable long-term learnings.
2. **Summarization-based** (beads): Old entries are summarized, preserving knowledge while reducing tokens. Elegant but requires LLM processing.
3. **Status-based** (pskoett): Entries progress through statuses. Once "promoted" to CLAUDE.md, the original entry can be archived. The knowledge lives on in its promoted form.

**Recommended approach for v3**: Status-based decay with time guards.
- `signal` entries older than 14 days with no promotion are auto-pruned (they were noise).
- `candidate` entries older than 30 days are flagged for review in the next `/reflect` run.
- `confirmed` entries are never auto-pruned (user validated them).
- `promoted` entries are archived (moved to an archive file or marked `archived`). The knowledge persists in CLAUDE.md.

This means the active memory store stays bounded: it contains only recent signals, active candidates, and confirmed-but-not-yet-promoted entries.

## 4. Retrieval Patterns

### 4.1 Current State: Full File Scan

The v2 plan has `/reflect` read `signals.jsonl` in its entirety. For a single session's worth of signals (tens to low hundreds of entries), this is fine. But cross-session accumulation changes the math.

### 4.2 Progressive Disclosure (claude-mem's 3-layer approach)

claude-mem's 3-layer retrieval (search -> timeline -> detail) is designed for a system with thousands of observations. It's the right architecture for a production memory system but over-engineered for v3, which will have hundreds of entries at most in the first months of use.

However, the _principle_ is sound and can be applied simply:

1. **Index layer**: A compact summary of what's in memory (category counts, recent entries, high-confidence patterns). Loaded cheaply.
2. **Filter layer**: Query by status, type, date range, or keyword. Returns entry IDs + one-line summaries.
3. **Detail layer**: Load full entries by ID for `/reflect` analysis.

### 4.3 Recommended Retrieval for v3

**Phase 1 (launch)**: Full scan with pre-filtering.
- `/reflect` reads the JSONL file, filters by status (skip `promoted`/`archived`), and processes the remainder.
- For files under 500 entries, this completes in milliseconds and consumes acceptable context.
- A helper script (`query-memory.py`) provides CLI filtering: `query-memory.py --status candidate --since 7d --type correction`

**Phase 2 (when memory exceeds ~500 entries)**: Indexed retrieval.
- Migrate to SQLite with FTS5. The JSONL remains as a write-ahead log; a sync script imports new entries into SQLite.
- `/reflect` queries SQLite instead of scanning JSONL.
- The migration script reads existing JSONL and populates the database. No data loss, no format change for hooks.

**Phase 3 (optional, future)**: Semantic search.
- Add vector embeddings (via an optional dependency like `sentence-transformers` or an API call).
- Enables queries like "what do I know about testing patterns" without exact keyword matches.
- This is explicitly out of scope for v3 but the storage format should not preclude it.

### 4.4 What "Good Enough for v3" Looks Like

The v3 system will realistically accumulate:
- ~10-50 signals per session (hooks capture liberally)
- ~5-15 candidates per `/reflect` run (after dedup and filtering)
- ~2-5 confirmed entries per session (user approves)

After 100 sessions, that's ~500 confirmed entries and ~1500 candidates (many pruned). A JSONL file of 2000 entries is ~200KB -- trivially scannable. SQLite becomes valuable around 5000+ entries or when a dashboard needs to query.

**Verdict**: JSONL with status-based filtering is sufficient for v3 launch. Design the schema so migration to SQLite is mechanical.

## 5. Extensibility Boundary

### 5.1 Design Principle: Schema-First, Storage-Second

The critical design decision is not "JSONL vs SQLite" -- it's defining a stable schema for learning entries that works across both. If the schema is right, storage is swappable.

### 5.2 Recommended Entry Schema

```jsonl
{
  "id": "sig-20260211-001",
  "version": 1,
  "timestamp": "2026-02-11T10:23:00Z",
  "session_id": "abc123",
  "type": "correction|failure|convention|command|gotcha|discovery|pattern",
  "status": "signal|candidate|confirmed|promoted|archived",
  "confidence": 0,
  "source": {
    "hook": "PreCompact|PostToolUseFailure|SessionEnd",
    "turn": 42,
    "file": "/path/to/relevant/file"
  },
  "context": "User said: 'No, use pnpm not npm in this project'",
  "summary": "Use pnpm, not npm, in this project",
  "category": "command|convention|gotcha|preference|project-structure",
  "tags": ["package-manager", "pnpm"],
  "related": ["sig-20260210-003"],
  "promoted_to": null,
  "meta": {}
}
```

**Schema design decisions**:
- `version` field enables schema evolution without breaking old entries.
- `id` format is `type_prefix-date-sequence`, human-readable and sortable. No hash-based IDs needed since we don't have multi-agent merge conflicts (hooks write to a session-partitioned log).
- `status` is the primary lifecycle field. All queries filter on it.
- `confidence` is an integer (0 = unscored, 1-5 = scored by `/reflect`). Kept as a number rather than an enum to allow future refinement.
- `source` captures provenance. A dashboard can show "where do learnings come from?" breakdowns.
- `summary` is the one-line version suitable for index/overview display. `context` is the full detail.
- `related` enables the cross-reference graph that pskoett uses for dedup and skill extraction.
- `promoted_to` tracks where a learning went (e.g., "project CLAUDE.md", "skill: pnpm-usage").
- `meta` is an escape hatch for future fields without schema changes.

### 5.3 Interface Boundary

The storage layer should expose these operations, regardless of whether the backend is JSONL or SQLite:

```
append(entry)                          # Write a new entry (hooks use this)
query(status, type, since, tags)       # Filter entries (reflect uses this)
get(id)                                # Fetch single entry by ID
update(id, fields)                     # Update status, confidence, etc.
archive(before_date, status_filter)    # Bulk archive/prune
stats()                                # Counts by status, type, category
export(format)                         # Dump to JSONL/CSV for dashboards
```

For v3, these are implemented as a Python module (`memory_store.py`) that reads/writes JSONL. A future version swaps the implementation to SQLite without changing the interface. Hooks call `append()` directly (or via a thin CLI wrapper). `/reflect` calls `query()` and `update()`.

### 5.4 Dashboard Compatibility

A future dashboard needs to:
1. **Read** the memory store (JSONL is parseable by any language; SQLite is queryable by any tool)
2. **Aggregate** by type, status, category, date (the schema supports all of these as first-class fields)
3. **Visualize** trends (confidence distribution, learning rate over time, common categories)
4. **Search** by keyword (grep on JSONL; FTS5 on SQLite)

The JSONL format is dashboard-compatible today -- a simple web app can parse it with `JSON.parse()` line by line. SQLite makes aggregation faster but isn't required until the dataset grows.

### 5.5 Migration Path

```
v3 launch          v3.1 (optional)         v3.2 (optional)
JSONL + Python  -> SQLite + FTS5        -> + Vector embeddings
query-memory.py    memory_store.py          semantic-search.py
                   (swap implementation)    (add embedding column)
                   import-jsonl.py          (optional dependency)
                   (one-time migration)
```

Each step is additive. No data loss. No schema change. The JSONL file can remain as a write-ahead log even after SQLite is introduced (hooks append to JSONL; a sync job imports to SQLite).

## 6. Recommendation for v3

### Storage: JSONL with stable schema

- **Primary store**: `~/.claude/reflections/memory.jsonl` (replaces `signals.jsonl` from v2)
- **Schema**: As defined in section 5.2, with `version: 1`
- **Index file**: `~/.claude/reflections/memory-index.md` -- auto-generated markdown summary updated by `/reflect` after each run. Contains category counts, recent confirmed entries, and top patterns. This is the "human-readable dashboard" for v3.
- **Archive**: `~/.claude/reflections/memory-archive.jsonl` -- promoted/archived entries moved here to keep the active file small.

### Retrieval: Full scan with pre-filtering

- Hooks write raw `signal` entries to `memory.jsonl`
- `/reflect` reads `memory.jsonl`, filters by status, processes with LLM intelligence
- A helper script provides CLI querying for debugging and inspection
- The index file provides a quick overview without loading the full log

### Cross-session learning: Status-based lifecycle

- Signals -> Candidates -> Confirmed -> Promoted -> Archived
- Confidence scoring via application count (simple integer)
- Two-tier deduplication (substring in hooks, semantic in `/reflect`)
- Time-based pruning for unreviewed signals (14 days), review reminders for stale candidates (30 days)

### Extensibility: Interface boundary + stable schema

- `memory_store.py` abstracts storage operations
- JSONL is the v3 backend; SQLite is the v3.1 backend
- Schema `version` field enables evolution
- `meta` field provides escape hatch
- All fields are dashboard-friendly (filterable, aggregatable, searchable)

### What we explicitly defer

- SQLite (not needed until ~5000 entries)
- Vector search / semantic embeddings (optional future extension)
- MCP server (claude-mem's approach; too heavy for skill-only system)
- Multi-agent merge (beads' hash-based IDs; not needed for single-user system)
- Real-time dashboard (the index file + CLI query tool are sufficient for v3)

## 7. Open Questions and Risks

### Open Questions

1. **Interaction with Claude Code Auto Memory**: The official auto memory system (`~/.claude/projects/<project>/memory/MEMORY.md`) now ships built-in. Should v3 write to auto memory instead of its own store? Or complement it? The auto memory system has no structured format, no confidence scoring, and no lifecycle -- but it's loaded automatically. Our system could _feed_ auto memory as a promotion target (learnings graduate from our structured store into the project's `MEMORY.md`).

2. **JSONL file locking**: Concurrent sessions appending to the same JSONL file could interleave entries. Options: (a) use `flock` in hook scripts, (b) partition by session ID in filename (`memory-{session_id}.jsonl`) and merge during `/reflect`, (c) accept rare interleaving as benign (each entry is a complete JSON line). Recommendation: (c) for v3 -- interleaved valid JSON lines are still parseable. Add `flock` if users report issues.

3. **Schema versioning strategy**: When we add fields in v3.1, do old entries get backfilled? Recommendation: No. New fields have defaults. The query layer handles missing fields gracefully. The `version` field tells consumers which fields to expect.

4. **Memory size budget**: How much context can `/reflect` consume when loading memory? If confirmed entries grow to 500 at ~100 tokens each, that's 50K tokens just for memory. Recommendation: `/reflect` loads summaries first (the `summary` field), then fetches full `context` only for entries it decides to act on. This is progressive disclosure applied within our own system.

### Risks

1. **Premature optimization**: SQLite, vector search, and dashboards are all deferred. If user demand materializes faster than expected, the migration path must actually work. Mitigation: The schema is designed to be SQLite-compatible from day one. Test the migration script early.

2. **JSONL scan performance**: At ~10K entries, full scan in Python takes ~100ms. At ~100K entries, it takes ~1s. This is acceptable for `/reflect` (runs once per session) but would be too slow for a real-time dashboard. Mitigation: The SQLite migration path exists for this scenario.

3. **Noise ratio**: Liberal signal capture (the design philosophy from v2) means most signals are noise. If the noise ratio exceeds 90%, the `/reflect` LLM analysis burns tokens on junk. Mitigation: Tier-1 dedup in hooks, aggressive pruning of unreviewed signals, and the `status` lifecycle ensure only validated entries accumulate.

4. **Stale knowledge**: A confirmed learning from 6 months ago might be wrong today (dependency upgraded, convention changed). Unlike code, learnings have no automated staleness detection. Mitigation: Periodic review prompts in `/reflect` for entries older than 90 days. User can re-confirm or archive.

## 8. Sources

- [claude-mem (thedotmack)](https://github.com/thedotmack/claude-mem) -- SQLite + FTS5 + Chroma, progressive disclosure, MCP server
- [pskoett self-improvement skill](https://github.com/pskoett/pskoett-ai-skills/tree/main/skills/self-improvement) -- Structured markdown, knowledge promotion, skill extraction
- [agent-playbook self-improving-agent (zhaono1)](https://github.com/zhaono1/agent-playbook/tree/main/skills/self-improving-agent) -- JSON memory types, confidence scoring, experience extraction
- [beads (steveyegge)](https://github.com/steveyegge/beads) -- Dolt versioned SQL, JSONL portability, hash-based IDs, memory decay
- [Claude Code Memory Documentation](https://code.claude.com/docs/en/memory) -- Official auto memory, MEMORY.md, 200-line limit
- [Letta Agent Memory Architecture](https://www.letta.com/blog/agent-memory) -- Core/recall/archival memory types, context engineering principles
- [Mem0 Paper (arxiv 2504.19413)](https://arxiv.org/pdf/2504.19413) -- Production agent memory with scalable long-term storage
- [Persistent Memory for Claude Code Setup Guide (Agent Native, Jan 2026)](https://agentnativedev.medium.com/persistent-memory-for-claude-code-never-lose-context-setup-guide-2cb6c7f92c58)
- [Claude Cognitive Memory System (Dec 2025)](https://eu.36kr.com/en/p/3647435834838663)
