#!/usr/bin/env bash
# Asserts that pipeline code in src/mal_payments/ is under 500 lines.
# Excludes mock_data.py (test fixture generator, not pipeline code) and
# __init__.py files (boilerplate). Counts non-empty, non-comment lines.

set -euo pipefail

LIMIT=500

count() {
  # Count non-blank, non-comment-only lines
  grep -vE '^\s*(#|$)' "$1" | wc -l
}

total=0
declare -a files

while IFS= read -r -d '' file; do
  base=$(basename "$file")
  if [[ "$base" == "__init__.py" || "$base" == "mock_data.py" ]]; then
    continue
  fi
  lines=$(count "$file")
  printf "%5d  %s\n" "$lines" "$file"
  total=$((total + lines))
  files+=("$file")
done < <(find src/mal_payments -name '*.py' -print0)

echo "------"
printf "%5d  TOTAL (limit: %d)\n" "$total" "$LIMIT"

if (( total > LIMIT )); then
  echo "FAIL: pipeline exceeds ${LIMIT}-line budget by $((total - LIMIT)) lines" >&2
  exit 1
fi

echo "OK: pipeline within ${LIMIT}-line budget ($((LIMIT - total)) lines remaining)"
