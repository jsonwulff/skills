#!/usr/bin/env bash
# capture-failure.sh — PostToolUseFailure hook (async, 5s timeout)
# Appends tool failure signals to signals.jsonl via memory_store.py.

set -euo pipefail

HOOK_DIR="$(cd "$(dirname "$0")" && pwd)"
MEMORY_STORE="$HOOK_DIR/memory_store.py"

# Check python3 availability
if ! command -v python3 &>/dev/null; then
    echo '{"hookSpecificOutput":{"hookEventName":"PostToolUseFailure","additionalContext":"Self-improvement hooks require Python 3 but it was not found. Signal capture is disabled. Install Python 3 or run /reflect-toggle to disable hooks."}}' >&2
    exit 0
fi

# Read hook input from stdin
INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_name','unknown'))" 2>/dev/null || echo "unknown")
ERROR=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('error','')[:200])" 2>/dev/null || echo "")
SESSION_ID=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('session_id',''))" 2>/dev/null || echo "")

# Skip if we couldn't extract meaningful data
if [ -z "$ERROR" ] && [ "$TOOL_NAME" = "unknown" ]; then
    exit 0
fi

ENTRY=$(python3 -c "
import json
print(json.dumps({
    'type': 'failure',
    'status': 'captured',
    'confidence': 1,
    'source': {'hook': 'PostToolUseFailure'},
    'content': '$TOOL_NAME failed: $(echo "$ERROR" | head -c 100 | tr -d "'" | tr -d '"')',
    'context': '$(echo "$ERROR" | head -c 200 | tr -d "'" | tr -d '"')',
    'session_id': '$SESSION_ID',
    'category': '',
    'tags': ['$TOOL_NAME']
}))
")

python3 "$MEMORY_STORE" append "$ENTRY" >/dev/null 2>&1

exit 0
