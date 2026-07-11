# Contributing to Culvert

Thanks for your interest. Culvert is early (0.1.x) and moving quickly; small,
focused contributions land fastest.

## Ground rules

- **One concern per PR.** If the title needs an "and", split it.
- **Green suite is the bar.** Java: `mvn -f data-pipeline-libraries-java/pom.xml
  test` (all modules). Python: `pytest` per touched library. New behaviour
  needs a test that fails without your change.
- **Contracts are the seam.** Business logic depends on contracts
  (`docs/CONTRACT.md`), never on a cloud SDK. Cloud specifics live in adapter
  modules; adapters bind the shared contract-test suites.
- **Honesty over polish.** If an adapter can't support a contract method,
  throw `UnsupportedOperationException` with the reason — never fake a partial
  implementation. Limitations are documented where they live.

## Getting started (fully local — no cloud account)

```bash
# Java (JDK 17+; Maven wrapper provisioning)
mvn -f data-pipeline-libraries-java/pom.xml install
mvn -f data-pipeline-libraries-java/pom.xml -P it verify   # emulators + LocalStack; needs Docker

# Python
python3 -m venv .venv && source .venv/bin/activate
pip install -e data-pipeline-libraries/data-pipeline-core pytest
pytest data-pipeline-libraries/data-pipeline-core/tests
```

Everything runs against emulators (Tier 1 in
`docs/framework-evolution/14-execution-tiers.md`); cloud is for proving, not
developing.

## Where things live

- `data-pipeline-libraries-java/` — Java reactor (contracts + adapters)
- `data-pipeline-libraries/` — Python libraries (packaged to PyPI as `culvert`
  from `python-culvert/`)
- `deployments/` — worked example pipelines, each with its own terraform/ + helm/
- `docs/framework-evolution/` — the why/what/when; disagreements resolve in its favour

## Releases

Maintainer-gated and coordinated across Maven Central + PyPI — see
`RELEASE.md`. Contributors never need publishing credentials.
