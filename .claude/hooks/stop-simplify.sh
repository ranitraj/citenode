#!/usr/bin/env bash
# Stop hook: nudge Claude to run /simplify when stopping with uncommitted changes.
set -euo pipefail

# Sweep stale markers so /tmp doesn't accumulate across sessions.
find "${TMPDIR:-/tmp}" -maxdepth 1 -name 'claude-simplify-*' -mtime +7 -delete 2>/dev/null || true

INPUT=$(cat)
SID=$(python3 -c 'import json,sys;print(json.load(sys.stdin).get("session_id","unknown"))' <<<"$INPUT" 2>/dev/null || echo unknown)
MARKER="${TMPDIR:-/tmp}/claude-simplify-${SID}"

# Once-per-session marker prevents looping when /simplify's own edits re-trigger Stop.
[ -f "$MARKER" ] && exit 0
[ -z "$(git status --porcelain 2>/dev/null)" ] && exit 0

touch "$MARKER"
cat <<'JSON'
{"decision":"block","reason":"You have uncommitted changes this session. Run /simplify before stopping — it catches code duplication, missed reuse opportunities, and inconsistent parameter ordering that accumulate as context grows."}
JSON
