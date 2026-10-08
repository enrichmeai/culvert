#!/usr/bin/env bash
# Run the Phase 3 proof harness (#232) from deployments/reference-e2e-gcp.
#
#   proof/run-proof.sh [harness options]
#   proof/run-proof.sh --airflow=/path/to/venv/bin/airflow --reset
#
# It compiles the module, builds the runtime classpath, and runs ProofHarness with it. Options are
# described in proof/README.md. MVN_OFFLINE=1 adds -o to the Maven calls.
set -euo pipefail
cd "$(dirname "$0")/.."
offline=${MVN_OFFLINE:+-o}
mvn -q $offline compile
mvn -q $offline dependency:build-classpath -Dmdep.outputFile=target/proof-classpath.txt -Dmdep.includeScope=runtime
exec java -cp "target/classes:$(cat target/proof-classpath.txt)" \
  -Dorg.slf4j.simpleLogger.defaultLogLevel=error \
  com.enrichmeai.culvert.e2e.proof.ProofHarness "$@"
