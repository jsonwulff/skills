#!/usr/bin/env bash
# inject-signals.sh — SessionStart hook (matcher: "compact")
# After compaction, injects captured signals as additionalContext
# so they survive in the post-compaction context.

set -euo pipefail

HOOK_DIR="$(cd "$(dirname "$0")" && pwd)"
MEMORY_STORE="$HOOK_DIR/memory_store.py"

# Check dependencies
if ! command -v python3 &>/dev/null; then
    echo '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"Self-improvement hooks require Python 3 but it was not found. Signal capture is disabled. Install Python 3 or run /reflect-toggle to disable hooks."}}'
    exit 0
fi

if ! command -v jq &>/dev/null; then
    echo '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"Self-improvement hooks require jq but it was not found. Run `brew install jq` (macOS) or `apt install jq` (Linux) to enable full signal capture."}}'
    exit 0
fi

# Read hook input from stdin
INPUT=$(cat)
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // empty')

if [ -z "$SESSION_ID" ]; then
    exit 0
fi

# Query signals for current session
SIGNALS=$(python3 "$MEMORY_STORE" query --status captured --session "$SESSION_ID" 2>/dev/null || echo "[]")

# Check if there are any signals
COUNT=$(echo "$SIGNALS" | jq 'length')
if [ "$COUNT" = "0" ] || [ -z "$COUNT" ]; then
    exit 0
fi

# Format compact summary
SUMMARY=$(echo "$SIGNALS" | python3 -c "
import sys, json
signals = json.load(sys.stdin)
lines = []
for s in signals[-20:]:  # Last 20 signals max
    t = s.get('type', '?')
    c = s.get('content', '')[:80]
    lines.append(f'- [{t}] {c}')
print('Self-improvement signals captured before compaction:')
print('\n'.join(lines))
print('\nRun /reflect to review and persist these learnings.')
")

# Output additionalContext JSON
jq -n --arg ctx "$SUMMARY" '{
    hookSpecificOutput: {
        hookEventName: "SessionStart",
        additionalContext: $ctx
    }
}'
