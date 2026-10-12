#!/usr/bin/env bash
# Stop: before Claude ends a turn, run the fast gates for what this branch touches, and feed any
# failure back. Ported from enrichmeai/valuedocs (2026-09-26), Gradle swapped for this repo's Maven reactor.
#   - Java: `mvn test-compile` (main + test sources, no tests run) for each reactor module with a
#     changed *.java / pom.xml, with -am so upstream modules it depends on are built too;
#   - Python: the unit tests of each package listed in .claude/hooks/fast-pytest.txt that
#     changed — only packages whose suite is offline and runs in seconds;
#   - .claude/hooks/ or .claude/settings.json changed: .claude/hooks/test-hooks.sh (#251).
# A gate whose tool is missing (no mvn, no pytest) or whose dependencies cannot be downloaded is
# reported as NOT RUN in a systemMessage — never as passed, and never skipped silently.
# Scoped on purpose — full suites and `mvn -P it verify` belong in CI or to Joseph (CLAUDE.md).
#   - change set = diff vs the merge-base with origin/main, plus uncommitted and untracked files;
#   - skipped when that change set is identical to the last one that passed;
#   - one retry only: if a stop was already blocked (stop_hook_active) and it still fails, the stop
#     is allowed with a warning, so a broken build can never loop forever.
# Opt out for one session: CLAUDE_SKIP_STOP_COMPILE=1.
set -uo pipefail

[ "${CLAUDE_SKIP_STOP_COMPILE:-}" = "1" ] && exit 0
input=$(cat)
active=$(printf '%s' "$input" | jq -r '.stop_hook_active // false')

root="${CLAUDE_PROJECT_DIR:-$(pwd)}"
cd "$root" || exit 0

base=$(git merge-base HEAD origin/main 2>/dev/null || echo HEAD)
all_changed=$( { git diff --name-only "$base" 2>/dev/null; git ls-files --others --exclude-standard 2>/dev/null; } | sort -u)
[ -z "$all_changed" ] && exit 0

# Reactor modules to compile: the nearest directory above each changed file that has a pom.xml,
# excluding the aggregator poms themselves (root and data-pipeline-libraries-java/).
modules=""
notrun=""
java_changed=$(printf '%s\n' "$all_changed" | grep -E '\.java$|(^|/)pom\.xml$' || true)
if [ -n "$java_changed" ] && [ -f pom.xml ] && ! command -v mvn >/dev/null 2>&1; then
  notrun="Java compile gate did NOT run: mvn is not installed, and this branch changes Java or a pom.xml — report it as not run."
fi
if command -v mvn >/dev/null 2>&1 && [ -f pom.xml ]; then
  for f in $(printf '%s\n' "$all_changed" | grep -E '\.java$|(^|/)pom\.xml$'); do
    d=$(dirname "$f")
    while [ "$d" != "." ] && [ ! -f "$d/pom.xml" ]; do d=$(dirname "$d"); done
    case "$d" in .|data-pipeline-libraries-java) continue ;; esac
    modules+="$d"$'\n'
  done
  modules=$(printf '%s' "$modules" | sort -u | paste -sd, -)
fi

# Python packages with a fast, offline suite.
comps=""
if [ -f .claude/hooks/fast-pytest.txt ]; then
  for c in $(grep -Ev '^[[:space:]]*(#|$)' .claude/hooks/fast-pytest.txt); do
    printf '%s\n' "$all_changed" | grep -q "^$c/.*\.py$" && comps+=" $c"
  done
fi
# The hooks' own fixture tests, when a hook or the settings that wire them changed.
hooktests=""
printf '%s\n' "$all_changed" | grep -qE '^\.claude/(hooks/|settings\.json$)' && [ -x .claude/hooks/test-hooks.sh ] && hooktests=1

if [ -z "$modules$comps$hooktests" ]; then
  [ -n "$notrun" ] && jq -n --arg m "$notrun" '{systemMessage: $m}'
  exit 0
fi

changed=$(printf '%s\n' "$all_changed" | grep -E '\.java$|(^|/)pom\.xml$|\.py$|^\.claude/' || true)
stamp_file="$(git rev-parse --git-dir)/claude-stop-check.stamp"
stamp=$( { echo "$modules|$comps|$hooktests"; for f in $changed; do [ -f "$f" ] && { echo "$f"; cat "$f"; }; done; } | sha256sum | cut -d' ' -f1)
[ -f "$stamp_file" ] && [ "$(cat "$stamp_file")" = "$stamp" ] && [ -z "$notrun" ] && exit 0

msg=""
if [ -n "$hooktests" ] && ! out=$(.claude/hooks/test-hooks.sh 2>&1); then
  msg+=".claude/hooks/test-hooks.sh failed:"$'\n'"$(printf '%s' "$out" | grep -E '^FAIL|hook tests:' | head -40)"$'\n'
fi
if [ -n "$modules" ] && ! out=$(mvn -B -q -pl "$modules" -am test-compile 2>&1); then
  if printf '%s' "$out" | grep -qE 'Could not resolve|Could not transfer|Could not find artifact|Connection (refused|reset|timed out)|UnknownHostException|Could not find the selected project'; then
    # The environment, not the code: say the gate did not run — never that it passed.
    notrun="Java compile gate did NOT run (dependency download failed or module not in the reactor) for $modules — report it as not run."
  else
    msg+=$(printf 'mvn test-compile failed for %s:\n%s\n' "$modules" "$(printf '%s' "$out" | grep -E '\[ERROR\]' | grep -vE 'To see the full stack|Re-run Maven|For more information|After correcting|resume the build|\[Help [0-9]|^\[ERROR\] *$' | head -60)")
  fi
fi
for c in $comps; do
  if ! python3 -m pytest --version >/dev/null 2>&1; then
    notrun+=$'\n'"pytest gate did NOT run for $c (pytest not installed): pip install -e '$c[test]'"; continue
  fi
  if ! out=$(cd "$c" && python3 -m pytest tests -q -x -p no:cacheprovider 2>&1); then
    if printf '%s' "$out" | grep -qE "ModuleNotFoundError: No module named '(data_pipeline_|culvert)"; then
      notrun+=$'\n'"pytest gate did NOT run for $c (package not installed): pip install -e '$c[test]'"
    else
      msg+=$'\n'"pytest $c/tests failed:"$'\n'"$(printf '%s' "$out" | tail -40)"
    fi
  fi
done

if [ -z "$msg" ]; then
  if [ -n "$notrun" ]; then jq -n --arg m "$notrun" '{systemMessage: $m}'; exit 0; fi
  echo "$stamp" > "$stamp_file"
  exit 0
fi
[ -n "$notrun" ] && msg+=$'\n'"$notrun"
if [ "$active" = "true" ]; then
  jq -n --arg m "$msg" '{systemMessage: ("Stop allowed, but the fast gates still fail — treat this turn as BLOCKED.\n" + $m)}'
  exit 0
fi
jq -n --arg m "$msg" '{decision: "block", reason: ($m + "\nFix these, or if this is attempt 3, stop and write the Blocker summary (CLAUDE.md § \"Autonomous build loop\").")}'
exit 0
