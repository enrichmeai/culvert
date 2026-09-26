#!/usr/bin/env bash
# PostToolUse(Edit|Write|MultiEdit): the fast checks for the one file just edited, so an error
# reaches Claude on the edit that caused it rather than at the end of the task.
# Ported from enrichmeai/valuedocs (2026-09-26).
#
# Exit 2 + stderr = the output is fed back to Claude (docs: code.claude.com/docs/en/hooks).
# Only the edited file is judged: an error elsewhere in the tree is not this edit's, and blocking on
# it would stall every edit. Java is deliberately absent — compiling is too slow per edit; the Stop
# hook (stop-fast-gates.sh) compiles the touched reactor modules once per turn.
set -uo pipefail

file=$(jq -r '.tool_input.file_path // empty')
[ -z "$file" ] || [ ! -f "$file" ] && exit 0

root="${CLAUDE_PROJECT_DIR:-$(git -C "$(dirname "$file")" rev-parse --show-toplevel 2>/dev/null)}"
rel="${file#"$root"/}"
out=""
fail=0

case "$rel" in
  *.py)
    if ! o=$(python3 -m py_compile "$file" 2>&1); then out+=$'python syntax:\n'"$o"$'\n'; fail=1
    elif command -v flake8 >/dev/null 2>&1 && [ -f "$root/.flake8" ]; then
      # The repo's own config (.flake8), run from the root so its excludes and per-file-ignores apply.
      if ! o=$(cd "$root" && flake8 "$rel" 2>&1); then out+=$'flake8 (.flake8):\n'"$o"$'\n'; fail=1; fi
    fi
    ;;
  *.json)
    if ! o=$(jq empty "$file" 2>&1); then out+=$'invalid JSON:\n'"$o"$'\n'; fail=1; fi
    ;;
  *.yml|*.yaml)
    # Helm templates are Go templates, not YAML, until rendered.
    case "$rel" in */templates/*) exit 0 ;; esac
    if python3 -c 'import yaml' 2>/dev/null; then
      if ! o=$(python3 -c 'import sys,yaml; list(yaml.safe_load_all(open(sys.argv[1])))' "$file" 2>&1); then
        out+=$'invalid YAML:\n'"$o"$'\n'; fail=1
      fi
    fi
    ;;
  *pom.xml)
    if command -v xmllint >/dev/null 2>&1; then
      if ! o=$(xmllint --noout "$file" 2>&1); then out+=$'invalid XML:\n'"$o"$'\n'; fail=1; fi
    elif ! o=$(python3 -c 'import sys,xml.dom.minidom as m; m.parse(sys.argv[1])' "$file" 2>&1); then
      out+=$'invalid XML:\n'"$o"$'\n'; fail=1
    fi
    ;;
esac

if [ "$fail" -ne 0 ]; then
  printf '%s\nFix these in %s before moving on.\n' "$out" "$rel" | head -c 8000 >&2
  exit 2
fi
exit 0
