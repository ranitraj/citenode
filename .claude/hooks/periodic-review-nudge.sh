#!/usr/bin/env bash
# PreToolUse hook for Edit|Write|MultiEdit.
# Fires ~15% of the time, nudging Claude to pause and ask the user to review
# accumulated changes before continuing. Silent drift compounds across many
# small edits, so periodic checkpoints catch drift early.
# See https://docs.claude.com/en/docs/claude-code/hooks
if (( RANDOM % 100 >= 15 )); then
  exit 0
fi
cat <<'JSON'
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "additionalContext": "Pause check: if several edits have landed since the user last reviewed direction, ask them to review the diff or current state and confirm before continuing. Small drifts compound."
  }
}
JSON
