# Release procedure — coordinated 0.1.0 (Java + Python)

Joseph triggers every publishing step manually. **Publishing is irreversible**:
PyPI version numbers can never be reused and Maven Central artifacts are
immutable. Nothing in this repo auto-publishes.

The release gate (authoritative:
[`docs/framework-evolution/13-python-parity-release.md`](docs/framework-evolution/13-python-parity-release.md) §2):
deploy → test end-to-end → validate libraries → **publish both ecosystems
together** → only then the book / release announcement.

---

## 0. State of the gate (update as steps complete)

| Step | Status |
|---|---|
| Reference deployments on real GCP (cloudrun-only) | ✅ 2026-07-10 — full ODP→FDP→CDP chain, event-driven |
| Libraries validated (unit + emulator IT + real-deploy exercise) | ✅ (the deploy caught 8 prod-only bugs; all fixed) |
| Composer one-day validation (the deliberate pre-publish spend) | ⬜ see §4 |
| PyPI publish | ✅ 2026-07-11 — culvert 0.1.0 live, verified from the index |
| Maven Central publish | ⬜ §3 |
| Book / announcement | ⬜ after both publishes |

## 1. Prerequisites (one-time, Joseph)

- **PyPI — trusted publishing (NO tokens).** A *pending publisher* for project
  `culvert` is registered (✅ 2026-07): owner `enrichmeai`, repo `culvert`,
  workflow `publish-pypi.yml`, environment `pypi`. Optional second gate:
  repo Settings → Environments → `pypi` → required reviewers → yourself.
- **Maven Central (Sonatype Central).** Account at central.sonatype.com;
  namespace `com.enrichmeai.culvert` verified; a portal user token; a GPG key
  whose **public** key is on a keyserver (`gpg --keyserver
  keyserver.ubuntu.com --send-keys <KEY_ID>`). Maven Central has **no OIDC**, so
  — unlike PyPI — publishing from git needs four **GitHub Actions secrets**
  (repo Settings → Secrets and variables → Actions). Add them yourself; agents
  never see them:

  | Secret | Value |
  |---|---|
  | `MAVEN_GPG_PRIVATE_KEY` | `gpg --export-secret-keys --armor <KEY_ID>` (the full ASCII block) |
  | `MAVEN_GPG_PASSPHRASE` | the key's passphrase |
  | `CENTRAL_USERNAME` | Sonatype portal token — username half |
  | `CENTRAL_PASSWORD` | Sonatype portal token — password half |

  Optional second gate: repo Settings → Environments → `maven-central` →
  required reviewers → yourself. Publishing locally instead needs no GitHub
  secret — put the token in `~/.m2/settings.xml` (server id `central`) and use
  §3's local command.
- **PyPI organization (optional, later).** The community-org `enrichmeai`
  request can proceed in parallel; transfer the `culvert` project into it when
  approved. Does not block 0.1.0.

## 2. Publish `culvert` to PyPI

The distribution is `python-culvert/` (single dist + extras — the D1
decision; all ten library import packages ship inside one wheel).

1. Confirm `main` is green and contains everything intended for 0.1.0.
2. GitHub → Actions → **publish-pypi** → *Run workflow* → type
   `publish-culvert` in the confirm box.
3. The `verify` job re-runs the full validation (build → `twine check` →
   clean-venv wheel install → `[gcp]` adapter-discovery smoke → sdist
   round-trip). The `publish` job only runs after verify is green, inside the
   protected `pypi` environment, via OIDC.
4. Post-publish check: `pip install culvert[gcp]` in a fresh venv from the
   real index; confirm `culvert.__version__` and that the project page
   renders.

If a broken release ships anyway: **yank** it on PyPI (never delete), fix,
release `0.1.1`.

## 3. Publish the Java reactor to Maven Central

**From git (preferred), once the §1 secrets are added:** GitHub → Actions →
**publish-maven** → *Run workflow* → type `publish-maven`. The `verify` job
builds the reactor and asserts every module carries main+sources+javadoc; the
`deploy` job (protected `maven-central` environment) imports the GPG key, signs,
and runs `mvn -P release deploy`.

**Locally (alternative, no GitHub secret):**

```bash
mvn -f data-pipeline-libraries-java/pom.xml -P release clean deploy
```

Either way:

- The `release` profile signs with GPG (loopback pinentry for headless CI) and
  uploads via `central-publishing-maven-plugin` with `autoPublish=false`.
- Sonatype Central holds the bundle in **validation** — review it at
  https://central.sonatype.com/, then click **Publish**. That portal
  confirmation is the Java point-of-no-return (a second human gate beyond the
  workflow trigger).
- Post-publish check: artifacts visible under `com.enrichmeai.culvert`; a
  scratch Maven project resolves `data-pipeline-core:0.1.0`.

## 4. Pre-publish Composer validation (one day, then teardown)

The single deliberate Composer spend (doc 13 §2a): apply
`infrastructure/terraform/systems/generic` with `enable_composer=true`,
deploy `deployments/data-pipeline-orchestrator/dags/culvert_dags.py`, verify
the DAGs parse and one ingestion DAG runs green on real Composer, capture
evidence, then re-apply with `enable_composer=false` — **same day**.
Everything else already runs cloudrun-only (no Airflow).

## 5. Coordinated order

1. §4 Composer validation (the last evidence for the gate)
2. §2 PyPI and §3 Maven Central in the same sitting — PyPI first (it has the
   stronger automated pre-verify); announce nothing between the two
3. Tag `v0.1.0` (`git tag v0.1.0 && git push --tags`); update
   [CHANGELOG.md](CHANGELOG.md) to a dated release; GitHub release notes with
   the honest status (two clouds: GCP full, AWS Java adapter family, Azure
   roadmap)
4. Book + Medium launch pieces follow the release, never precede it

## 6. Version discipline

- Reactor, Python dist, deployments and docs all say **0.1.0** before the
  trigger; verify with grep, not memory.
- After release, bump `main` in one PR: `mvn versions:set -DnewVersion=0.2.0-SNAPSHOT`
  (Java) and `version = "0.2.0.dev0"` in `python-culvert/pyproject.toml`.
