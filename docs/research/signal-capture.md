# Signal Capture Research: Learning Recognition & Signal Detection for v3

## 1. Taxonomy of Signal Types

Beyond the v2 plan's narrow focus on corrections and failures, learning signals fall into seven distinct categories. Each category has different detection difficulty, false positive rates, and value for agent improvement.

### 1.1 Corrections (User overrides Claude's approach)

**Examples:**
- "No, use pnpm not npm in this project"
- "That's wrong, the config file is in /etc not /opt"
- "Actually, we use camelCase here, not snake_case"

**Detection difficulty:** Low-Medium. Keyword heuristics catch many cases ("no,", "wrong", "actually", "instead", "should be", "use X instead").
**Value:** Very high. Corrections are the most reliable signal that Claude has a knowledge gap. They represent explicit user feedback with clear before/after states.
**False positive risk:** Medium. Phrases like "no" and "actually" appear in normal conversation without being corrections.

### 1.2 Failures (Tool/command errors)

**Examples:**
- `npm test` exits with non-zero status
- Edit tool fails because old_string not found
- Permission denied errors
- Import/module not found errors

**Detection difficulty:** Very low. Tool failures have explicit exit codes and error messages.
**Value:** Medium. Individual failures may be transient (typos, temporary state), but *repeated* failures on the same pattern are high-value signals.
**False positive risk:** Low for the event itself, high for the interpretation. A single `npm test` failure may not indicate a learnable pattern.

### 1.3 Conventions (Project-specific patterns and preferences)

**Examples:**
- "We always use absolute imports in this project"
- "Our convention is to put tests next to source files"
- User consistently uses specific commit message format
- User prefers a particular error handling pattern

**Detection difficulty:** Medium-High. Explicit statements ("always use", "our convention") are catchable by keywords. Implicit conventions (observed from repeated behavior) require pattern analysis across turns.
**Value:** High. Conventions reduce friction across all future sessions.
**False positive risk:** Medium. May capture one-off preferences as conventions.

### 1.4 Successful Patterns (Things that worked well)

**Examples:**
- Claude uses a particular debugging approach and user says "perfect, that's exactly right"
- A file structure decision that user approves enthusiastically
- A testing strategy that catches a bug effectively
- User rates a solution highly or expresses satisfaction

**Detection difficulty:** Medium. Positive affirmations ("yes", "perfect", "exactly", "that works") are somewhat detectable by keywords, but distinguishing genuine approval from conversational acknowledgment is hard.
**Value:** Medium-High. Reinforcing what works is as important as correcting what doesn't. The agent-playbook system tracks these via user ratings (>= 7/10 = reinforcement).
**False positive risk:** High. "yes" and "ok" are very common and usually don't indicate notable success.

### 1.5 Time Sinks (Tasks that took too many turns)

**Examples:**
- Same file edited 5+ times before getting it right
- Claude searches for a file across 4 different directories
- User has to explain the same concept multiple times
- A task that should be 2 turns takes 10

**Detection difficulty:** Medium. Measurable by counting: repeated edits to same file (3+), consecutive failed searches, high turn count relative to task complexity. The v2 plan already tracks "multi-attempt edits" (same file edited 3+ times).
**Value:** High. Time sinks directly indicate missing context that should be documented. If Claude repeatedly looks in the wrong place for config files, that's a CLAUDE.md entry waiting to happen.
**False positive risk:** Low-Medium. Some tasks genuinely require iteration (complex refactors), but repeated *searching* patterns are reliable indicators.

### 1.6 Missing Context (Claude had to ask or guess)

**Examples:**
- Claude asks "what package manager does this project use?"
- Claude guesses wrong about project structure and has to backtrack
- Claude doesn't know about a project-specific CLI tool
- Claude assumes a default that's wrong for this project

**Detection difficulty:** Medium. Claude's questions can be detected in its output, but distinguishing "appropriate clarification questions" from "should have known this" requires understanding what context should exist.
**Value:** Very high. Missing context signals are the most directly actionable -- they map 1:1 to CLAUDE.md entries or project documentation gaps.
**False positive risk:** Low. If Claude had to ask, the context was genuinely missing.

### 1.7 Tool/Workflow Preference Signals

**Examples:**
- User says "use grep instead of searching files one by one"
- User corrects Claude's git workflow ("always create a branch first")
- User prefers Edit over Write for modifications
- User wants tests run after every change

**Detection difficulty:** Medium. Often explicit ("use X", "prefer Y"), but sometimes implicit (user manually does something Claude should have done).
**Value:** High. Workflow preferences compound across sessions.
**False positive risk:** Low-Medium. Explicit preferences are reliable; inferred ones less so.

### Summary Table

| Signal Type | Detection Difficulty | Value | False Positive Risk | Best Capture Point |
|---|---|---|---|---|
| Corrections | Low-Medium | Very High | Medium | PreCompact (transcript scan) |
| Failures | Very Low | Medium | Low (event) / High (interpretation) | PostToolUseFailure (real-time) |
| Conventions | Medium-High | High | Medium | PreCompact + /reflect analysis |
| Successful Patterns | Medium | Medium-High | High | Stop / SessionEnd |
| Time Sinks | Medium | High | Low-Medium | PreCompact (turn counting) |
| Missing Context | Medium | Very High | Low | PreCompact (question detection) |
| Tool/Workflow Preferences | Medium | High | Low-Medium | PreCompact (transcript scan) |


## 2. Recognition Strategy Comparison

### 2.1 Spectrum: Cheap-to-Expensive

The approaches from our references and broader research form a clear spectrum from cheap pattern matching to expensive LLM-based classification.

| Approach | Cost | Accuracy | Latency | Used By |
|---|---|---|---|---|
| **Regex/keyword heuristics** | Near zero | Low (many false positives) | <100ms | v2 plan (capture-signals.py) |
| **Structured event logging** | Near zero | Medium (high for failures) | <10ms | v2 PostToolUseFailure hook |
| **Statistical counting** | Near zero | Medium | <100ms | v2 (multi-attempt edits), agent-playbook (3+ repetitions) |
| **Rule-based classification** | Low | Medium | <200ms | pskoett (priority/category assignment), claude-reflect (confidence levels) |
| **Every-event observation** | Medium | Medium-High | ~100ms/event | claude-mem (SQLite + every hook) |
| **LLM single-turn eval** | Medium-High | High | 1-3s | Prompt hooks (type: "prompt"), claude-diary (/diary) |
| **LLM multi-turn agent** | High | Very High | 5-30s | Agent hooks (type: "agent"), /reflect skill |

### 2.2 Reference Implementation Approaches

#### v2 Plan: Keyword Heuristics
- **Strategy:** Pattern matching on transcript text at PreCompact time
- **Signals detected:** Corrections ("no,", "wrong", "actually"), repeated failures (same tool 2+), multi-attempt edits (same file 3+), convention statements ("always use", "our convention"), command sharing (backtick-wrapped commands)
- **Strengths:** Zero runtime cost, simple to implement, catches explicit corrections reliably
- **Weaknesses:** Misses implicit corrections, nuanced preferences, successful patterns. "No" appears in normal conversation. Cannot distinguish "no, that's wrong" from "no, I meant the other file"
- **Philosophy:** Cheap capture, smart filtering at /reflect time

#### pskoett (Trigger-Based with Structured Logging)
- **Strategy:** Four distinct trigger categories with structured metadata (ID, priority, area, status)
- **Signals detected:** Corrections (user feedback phrases), feature requests ("can you also"), knowledge gaps ("that's outdated"), errors (non-zero exits, stack traces)
- **Strengths:** Rich metadata enables filtering. Priority system (critical/high/medium/low) focuses attention. Dedup via grep. Knowledge promotion lifecycle (learnings graduate to CLAUDE.md)
- **Weaknesses:** Relies on explicit user language patterns. More complex state management (IDs, statuses, linking). No statistical pattern detection
- **Philosophy:** Structured knowledge base with explicit lifecycle management

#### agent-playbook (Hook-Based with Confidence Scoring)
- **Strategy:** Hooks on skill completion (before_start, after_complete, on_error) with multi-memory architecture
- **Signals detected:** Performance signals (success/partial/failure), error signals (non-zero exits), feedback signals (user ratings 1-10), pattern signals (3+ repetitions), guidance accuracy (incorrect advice detection)
- **Strengths:** Confidence scoring (0.0-1.0) with application counting. 3+ repetition threshold before elevation. Self-correction loop when guidance fails. Distinction between concrete incidents and generalizable patterns
- **Weaknesses:** Requires explicit user ratings for feedback signals. Complex multi-memory architecture (semantic, episodic, working). May over-engineer for simpler use cases
- **Philosophy:** Statistical confidence through repetition, gradual promotion from observation to pattern to skill

#### claude-mem (Full Observation Capture)
- **Strategy:** Capture observations at every lifecycle event via 5 hooks (SessionStart, UserPromptSubmit, PostToolUse, Stop, SessionEnd)
- **Signals detected:** Everything -- observations captured on every tool use and interaction
- **Strengths:** No false negatives (captures everything). SQLite + Chroma for hybrid search. Progressive disclosure (index -> timeline -> detail) saves tokens. 10x token savings through filtering
- **Weaknesses:** High overhead (runs on every event). Requires background worker service (port 37777). External dependencies (Bun, Chroma). Most observations are noise
- **Philosophy:** Capture everything, filter at retrieval time

#### claude-reflect (Confidence-Based with Git Integration)
- **Strategy:** Stop hook triggers analysis; three confidence levels (HIGH/MEDIUM/LOW) based on language patterns
- **Signals detected:** Critical corrections ("use X instead of Y", "never do X"), approvals ("yes, perfect", "that works well"), observations ("have you considered...?")
- **Strengths:** Confidence levels map naturally to action urgency. Git-backed with timestamped backups. YAML validation prevents corruption. Clean approve/reject flow
- **Weaknesses:** Only fires at session end (Stop hook). Misses mid-session signals lost to compaction. Relies entirely on language pattern matching for confidence
- **Philosophy:** Conservative capture with strong safety nets (backups, validation, rollback)

#### claude-diary (Two-Phase Reflection)
- **Strategy:** Phase 1: /diary captures observations from conversation context. Phase 2: /reflect analyzes accumulated diary entries for patterns
- **Signals detected:** Eight categories -- task summary, work done, design decisions, user preferences, code review feedback, challenges, solutions, code patterns
- **Strengths:** Clean separation of capture (diary) and analysis (reflect). PreCompact hook catches signals before compaction. Pattern detection through repetition (2+ = pattern, 3+ = strong pattern). Focus on the "why" behind decisions
- **Weaknesses:** Two-command workflow may reduce adoption. Pattern detection requires multiple sessions of data
- **Philosophy:** "Subconscious" memory formation -- reflect after the fact without slowing immediate work

#### Implicit Memory (LLM Autonomous Capture)
- **Strategy:** Give the LLM tools to manage its own memory; let it decide what's worth remembering
- **Signals detected:** Whatever the LLM judges important based on contextual understanding
- **Strengths:** Highest accuracy -- leverages the LLM's full language understanding. No false negative problem. Self-correcting (catches own errors). Adapts to any domain without rule engineering
- **Weaknesses:** Highest cost -- LLM evaluation on every potential signal. Unpredictable behavior. Hard to audit what gets remembered and why. Requires trust in LLM judgment
- **Philosophy:** Trust the model's contextual intelligence within hard security boundaries

### 2.3 Research Literature Approaches

From the survey of self-evolving agents (EvoAgentX, 2025):
- **Self-Generated In-Context Examples:** Store full successful trajectories, replay as in-context examples. ALFWorld: 73% -> 89%. Conceptually similar to episodic memory in agent-playbook
- **Self-Challenging Agents:** Agent generates its own training tasks, solves them, stores successful solutions. Not directly applicable to v3 but the "challenge yourself" concept maps to "/reflect" proactively looking for gaps
- **Reward-based loops:** Use test results as scalar rewards for code tasks. Directly applicable -- test pass/fail is a clean signal

From LangMem (LangChain):
- **Active formation:** During conversation, adds latency but captures critical context immediately
- **Background formation:** Between interactions, deeper analysis without response-time impact. This is exactly the v3 model (/reflect runs outside active work)
- **Importance scoring:** Memories include importance indicators that affect retrieval ranking, not just semantic similarity
- **Memory consolidation:** Reconcile new information with existing beliefs through deletion, invalidation, updating, or consolidation. Prevents unbounded growth


## 3. Recommended Capture Approach for v3

### 3.1 Design Principle: Cheap Capture + Smart Filtering

Given the zero-overhead constraint, v3 should sit at the **left side of the spectrum during active work** (regex + event logging) and use **LLM intelligence only at /reflect time** (right side). This is already the v2 plan's philosophy, and it's the right one.

The key insight from this research is: **false positives at capture time are cheap, false negatives are expensive.** A noisy signal in `signals.jsonl` costs a few bytes of disk. A missed correction costs a recurring mistake across future sessions.

### 3.2 Three-Tier Architecture

**Tier 1: Real-time event capture (hooks, ~0 cost)**
- PostToolUseFailure: Log every tool failure (async, non-blocking)
- PostToolUse: Log file edits with repetition counting (async, track same-file-edit counts)
- Stop: Log session summary metadata (turn count, files touched, tools used)

**Tier 2: Transcript mining at compaction boundaries (PreCompact, <1s)**
- Run capture-signals.py with enhanced heuristics:
  - v2 keyword patterns for corrections and conventions
  - Question detection (Claude's output containing "?" after user asks nothing)
  - Turn-count anomalies (flag tasks taking >2x expected turns)
  - Search-failure patterns (multiple Glob/Grep with no results before finding target)
  - Positive reinforcement patterns (user approval after Claude's approach)
- All signals logged to signals.jsonl as raw candidates with type, context, and confidence

**Tier 3: LLM-powered analysis at /reflect time (on-demand, user-initiated)**
- Read signals.jsonl + conversation transcript
- LLM classifies, deduplicates, and prioritizes signals
- Proposes concrete improvements (CLAUDE.md entries, project changes)
- User approves/rejects in batch

### 3.3 Enhanced Heuristics for Tier 2

Building on v2's pattern set, add these detection rules:

| Pattern | Detection Rule | Signal Type |
|---|---|---|
| User correction | Message after Claude response containing: "no,", "wrong", "actually", "instead", "that's not", "should be", "use X instead" | correction |
| Repeated failure | Same tool failing 2+ times consecutively | failure_pattern |
| Multi-attempt edit | Same file edited 3+ times in sequence | time_sink |
| Convention statement | "always use", "we prefer", "our convention", "naming", "in this project" | convention |
| Command sharing | Backtick-wrapped commands, "run `X`" | command |
| Search thrashing | 3+ Glob/Grep calls with empty results before finding target | missing_context |
| Claude question | Claude asks a question that could have been answered by CLAUDE.md | missing_context |
| Positive reinforcement | User says "perfect", "exactly", "great" after Claude completes a multi-step task | successful_pattern |
| Workflow correction | "use X instead of Y" where X and Y are tools/commands | tool_preference |
| Repeated explanation | Same concept explained 2+ times in a session | documentation_gap |

### 3.4 Confidence Assignment

Borrow from agent-playbook's confidence scoring, but keep it simple at capture time:

- **high:** Explicit corrections with clear before/after ("use pnpm not npm")
- **medium:** Keyword-matched patterns with moderate context ("actually, the tests are in /tests")
- **low:** Statistical patterns (repeated edits, search thrashing) that may have innocent explanations

/reflect uses confidence as a hint for prioritization, not as a hard filter.


## 4. Hook Event Mapping with Cost/Benefit

### 4.1 Complete Event Analysis

| Hook Event | What Could Be Captured | Cost (time/overhead) | Benefit | Recommendation |
|---|---|---|---|---|
| **SessionStart** | Inject prior signals after compaction | Low (read file, format summary) | High (signals survive compaction) | **USE** -- essential for signal persistence |
| **UserPromptSubmit** | Detect user corrections, commands, preferences | Medium (regex on every prompt) | Medium | **SKIP** -- too frequent, same data available at PreCompact |
| **PreToolUse** | Nothing useful for learning | N/A | None | **SKIP** -- wrong purpose (blocking, not learning) |
| **PostToolUse** | Track edit patterns (same-file counts), successful searches | Low (async, just increment counter) | Medium | **CONSIDER** -- useful for time-sink detection, but adds complexity |
| **PostToolUseFailure** | Log tool failures with context | Very Low (async, append to file) | High | **USE** -- failures are high-signal, low-noise |
| **PreCompact** | Mine transcript for all signal types | Medium (Python script, <1s) | Very High | **USE** -- primary capture point, richest data source |
| **Notification** | Nothing useful for learning | N/A | None | **SKIP** -- wrong purpose |
| **SubagentStart/Stop** | Track subagent usage patterns | Low | Low | **SKIP** -- marginal value for v3 |
| **Stop** | Session summary, turn count, outcome | Low (quick metadata extraction) | Medium | **CONSIDER** -- useful for time-sink detection, but /reflect already runs here |
| **TaskCompleted** | Verify task quality | Medium | Low (for learning) | **SKIP** -- quality gates are a different concern |
| **TeammateIdle** | Nothing useful for learning | N/A | None | **SKIP** -- team coordination, not learning |
| **SessionEnd** | Final session metadata | Low | Low | **SKIP** -- PreCompact already captures transcript data |

### 4.2 Recommended Hook Set for v3

**Must have (from v2, validated by research):**

1. **PreCompact** (command, sync, 30s timeout) -- Primary transcript mining
   - Reads transcript JSONL, applies enhanced heuristics from section 3.3
   - Writes raw signal candidates to `~/.claude/reflections/signals.jsonl`
   - Runs before compaction so it has access to full transcript

2. **SessionStart** (command, sync, matcher: "compact") -- Signal persistence
   - Reads signals.jsonl, filters to current session
   - Returns `additionalContext` with signal summary
   - Ensures signals survive compaction

3. **PostToolUseFailure** (command, async, 5s timeout) -- Real-time failure logging
   - Appends failure entry to signals.jsonl
   - Async so it never blocks Claude's response

**Consider for v3.1:**

4. **PostToolUse** (command, async, matcher: "Edit|Write") -- Edit pattern tracking
   - Maintains a lightweight counter of per-file edit counts in a temp file
   - PreCompact reads this counter to detect multi-attempt edits more reliably than transcript scanning
   - Adds complexity but improves time-sink detection accuracy

5. **Stop** (command, async) -- Session outcome metadata
   - Logs total turn count, files modified, tools used to signals file
   - /reflect could use this for "was this session unusually long?"
   - Risk: fires frequently (every Claude response completion), needs `stop_hook_active` guard

### 4.3 What NOT to Hook (and Why)

- **UserPromptSubmit:** Fires on every user message. Same data is available in the transcript at PreCompact time. The cost of processing every prompt is not justified when we can batch-process at compaction
- **PreToolUse:** Designed for blocking/modifying tool calls, not observing. Learning capture should never interfere with tool execution
- **PostToolUse (all tools):** Too noisy. Every Read, Glob, Grep call generates an event. Only Edit/Write are worth tracking, and only for repetition counting
- **SessionEnd:** By the time SessionEnd fires, the user is leaving. Any capture should have happened at PreCompact or Stop. SessionEnd is for cleanup, not data collection


## 5. False Positive Management

### 5.1 The Noise Problem

Every system we studied has a noise problem, and they handle it differently:

| System | Strategy | Tradeoff |
|---|---|---|
| v2 plan | "Pattern matching produces false positives -- that's fine. /reflect filters them with LLM intelligence" | Simple, but signals.jsonl may grow large |
| pskoett | Priority filtering + dedup via grep + quality gates ("non-obvious solutions", "reproducibility") | More accurate, but requires more state management |
| agent-playbook | Confidence scoring (0.0-1.0) + 3+ repetition threshold before elevation | Statistical rigor, but needs multiple sessions of data |
| claude-mem | Capture everything, filter at retrieval time with progressive disclosure | No false negatives, but storage/retrieval cost |
| claude-reflect | Three confidence levels + user approval gate + git rollback | Conservative, but may miss low-confidence signals |
| claude-diary | 2+ occurrences = pattern, 3+ = strong pattern | Clean heuristic, but requires multi-session accumulation |

### 5.2 Cost of False Positives vs. False Negatives

In this specific context:

**False positive cost: LOW**
- A noisy signal in signals.jsonl costs a few bytes of storage
- At /reflect time, the LLM filters it out in milliseconds
- The user sees it as a rejected proposal (minor friction, quickly dismissed)
- Worst case: user rejects a bad proposal, loses 5 seconds

**False negative cost: HIGH**
- A missed correction means Claude repeats the mistake in every future session
- A missed convention means ongoing friction as Claude violates project norms
- Missing context that should be in CLAUDE.md means Claude asks the same questions repeatedly
- Worst case: user has to re-correct the same issue across many sessions

**Conclusion:** The system should be biased toward **over-capture** at the signal level and rely on /reflect + user approval to filter. This aligns with v2's philosophy and is validated by claude-mem's approach (capture everything, filter at retrieval).

### 5.3 Recommended Noise Management for v3

1. **At capture time (hooks):** Low-threshold heuristics. Accept false positives. Never miss a potential correction
2. **At storage time:** Include confidence level with each signal (high/medium/low) so /reflect can prioritize
3. **At analysis time (/reflect):** LLM-powered deduplication and classification. Cross-reference with existing CLAUDE.md entries to avoid proposing duplicates
4. **At proposal time:** Batch presentation with user approval. User can accept, reject, or modify each proposal
5. **Staleness management:** Signals older than 7 days auto-pruned. Processed signals marked or removed after /reflect runs
6. **Volume cap:** If signals.jsonl exceeds ~500 entries, oldest low-confidence signals are pruned first


## 6. Open Questions

### 6.1 Capture Granularity
Should PostToolUse tracking (for edit counting) be in v3.0 or deferred to v3.1? It adds a fourth hook but improves time-sink detection. The PreCompact transcript scan can already detect multi-attempt edits by counting Edit/Write calls to the same file, so the real question is whether real-time counting is significantly more reliable.

### 6.2 Cross-Session Pattern Detection
agent-playbook requires 3+ repetitions before elevating a pattern. claude-diary requires 2+ occurrences. What's the right threshold for v3? Should /reflect track signal frequency across sessions, or is single-session analysis sufficient for v3.0?

### 6.3 Positive Signal Detection
Successful patterns are high-value but have the highest false positive rate. Should v3.0 attempt to detect them, or focus on the more reliable correction/failure/convention signals first?

### 6.4 Signal Schema Evolution
The signals.jsonl format should be designed for forward compatibility. What fields beyond `{ts, sid, type, context, confidence, turn}` should be included from the start? Tool name? File path? User message hash (for dedup)?

### 6.5 Active vs. Background Formation
LangMem distinguishes "active" (during conversation) and "background" (between interactions) memory formation. v3 uses background formation exclusively (/reflect). Should there ever be an active path for critical corrections (e.g., when user says "NEVER do X")? The zero-overhead constraint suggests no, but some corrections are urgent enough that waiting for /reflect risks repeating the mistake in the same session.

### 6.6 Implicit Memory as Future Direction
The "implicit memory" approach (let the LLM decide what to remember) showed the highest accuracy in our research. Could v3 evolve toward this by replacing regex heuristics with prompt hooks (type: "prompt") at PreCompact time? The cost would increase from ~0 to ~1-3s per compaction, but accuracy would improve substantially. This may be a viable v3.1 or v4 direction.

### 6.7 Project-Side vs. Agent-Side Signals
The v3 plan distinguishes agent-side improvements (CLAUDE.md entries) from project-side improvements (file structure, naming, documentation). Should signal capture differentiate these at capture time, or should /reflect handle the classification? Capture-time differentiation would require understanding project structure, which seems better suited to /reflect's LLM analysis.


## References

- [v2 plan: Hook-Driven Self-Improvement System](/docs/plans/self-improvement-system-v2.md)
- [v3 plan: Memory-Driven Agent Learning](/docs/plans/self-improvement-system-v3.md)
- [pskoett/pskoett-ai-skills self-improvement](https://github.com/pskoett/pskoett-ai-skills/tree/main/skills/self-improvement)
- [zhaono1/agent-playbook self-improving-agent](https://github.com/zhaono1/agent-playbook/tree/main/skills/self-improving-agent)
- [thedotmack/claude-mem](https://github.com/thedotmack/claude-mem)
- [haddock-development/claude-reflect-system](https://github.com/haddock-development/claude-reflect-system)
- [rlancemartin/claude-diary](https://github.com/rlancemartin/claude-diary)
- [EvoAgentX/Awesome-Self-Evolving-Agents](https://github.com/EvoAgentX/Awesome-Self-Evolving-Agents) -- Comprehensive survey of self-evolving AI agents
- [Yohei Nakajima: Better Ways to Build Self-Improving AI Agents](https://yoheinakajima.com/better-ways-to-build-self-improving-ai-agents/)
- [LangChain LangMem Conceptual Guide](https://langchain-ai.github.io/langmem/concepts/conceptual_guide/)
- [Sam Keen: Implicit Memory Systems for LLMs](https://deepengineering.substack.com/p/implicit-memory-systems-for-llms)
- [Claude Code Hooks Reference](https://code.claude.com/docs/en/hooks)
