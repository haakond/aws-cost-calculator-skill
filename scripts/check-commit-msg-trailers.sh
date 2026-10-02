#!/usr/bin/env bash
# commit-msg hook: rejects co-author and assistant-attribution trailers. Commits in this repository carry the author identity only.
set -euo pipefail

pattern='^(co-authored-by:|claude-session:|🤖 generated with)'
status=0

for msg_file in "$@"; do
  if matches=$(grep -inE "$pattern" "$msg_file"); then
    status=1
    echo "Co-author or assistant-attribution trailer in commit message ($msg_file):"
    echo "$matches" | sed 's/^/  /'
  fi
done

exit "$status"
