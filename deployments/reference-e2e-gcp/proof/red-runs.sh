#!/usr/bin/env bash
# Red runs for the proof harness (#232): break one rule per scenario, run that scenario, restore.
# Every scenario must report FAIL. Arguments are passed to the harness (--airflow=..., or the
# --composer-env=... options, is needed for scenarios 4 and 6). Uses --reset: run it only against databases kept for the proof.
#
#   MVN_OFFLINE=1 proof/red-runs.sh --airflow=/path/to/venv/bin/airflow
set -u
cd "$(dirname "$0")/.."
run_java=src/main/java/com/enrichmeai/culvert/e2e/controlplane/ControlPlaneRun.java
dag=dags/reference_e2e_control_plane.py
work=$(mktemp -d)
cp "$run_java" "$work/ControlPlaneRun.java.orig"
restore() { cp "$work/ControlPlaneRun.java.orig" "$run_java"; }
trap restore EXIT

sed 's/        if _waiting_on:/        if False:  # BROKEN: the gate is never enforced/' "$dag" > "$work/dag-no-gate.py"
grep -v "max_active_tasks=2," "$dag" > "$work/dag-no-cap.py"

patch_java() { # python replacement: old new
  python3 - "$run_java" "$1" "$2" <<'PY'
import sys
path, old, new = sys.argv[1:]
s = open(path).read()
if old not in s:
    sys.exit("red-runs: the mutation no longer applies; update proof/red-runs.sh")
open(path, "w").write(s.replace(old, new, 1))
PY
}

failed=0
red() { # scenario label [harness args...]
  local n=$1 label=$2; shift 2
  echo "##### RED $n: $label"
  proof/run-proof.sh --reset --scenarios="$n" "$@" > "$work/red$n.log" 2>&1
  grep -E "\[FAIL\]|^  => " "$work/red$n.log"
  grep -q "^  => FAIL" "$work/red$n.log" || { echo "!!!!! scenario $n did NOT fail against its break"; failed=1; }
  restore
}

patch_java '            if (claimed instanceof ClaimResult.Held) {
                out.add(' '            if (claimed instanceof ClaimResult.Held) {
                // BROKEN: a held stage is worked anyway, without the claim
                if (runId == null) { runId = startJob(unit); run.runId = runId; }
                long worked = work(unit, stage, runId);
                out.add(new StageResult(unit, stage, Outcome.DONE, claimant, runId, worked, ""));
                continue;
            }
            if (false) {
                out.add('
red 1 "a held stage is worked without the claim" "$@"

patch_java '                long n;
                try {' '                claim.complete(); // BROKEN: completed before the work is done
                long n;
                try {'
patch_java '                claim.complete();
                total += n;' '                total += n;'
red 2 "the claim is completed before the stage's work" "$@"

red 3 "no idle_in_transaction_session_timeout on the server" "$@" --session-timeout=0
red 4 "the DAG's stage-gate check is removed" "$@" --dag="$work/dag-no-gate.py"

patch_java 'InputAttempt.retry(input, period, runId, verdict, status.runId().orElseThrow())' \
  'InputAttempt.of(input, period, runId, verdict) /* BROKEN: retry not declared */'
red 5 "a re-validation is not declared as a retry" "$@"

red 6 "the DAG has no max_active_tasks" "$@" --dag="$work/dag-no-cap.py"

patch_java '        if (runId != null) {
            store.jobControl().markFailed(runId, code, message, stage, Optional.empty());
        }' '        // BROKEN: failures are never recorded'
red 7 "job control never records a failure" "$@"

echo "logs: $work"
exit $failed
