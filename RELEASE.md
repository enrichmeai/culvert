# Release procedure

Internal procedure for publishing Culvert framework releases. **Not automated.** Joseph triggers each step manually.

## Prerequisites (one-time)

- **PyPI:** Create an API token at https://pypi.org/manage/account/token/. Store as the `PYPI_TOKEN` env var or in `~/.pypirc`.
- **Maven Central / Sonatype Central:** Create an account at https://central.sonatype.com/. Register the `com.enrichmeai.culvert` namespace (verification via DNS TXT on `enrichmeai.com`). Generate a user token. Set up GPG: `gpg --gen-key`, `gpg --export-secret-keys --armor <KEY_ID>` and add to `~/.m2/settings.xml` under the `central` server.
- **Re-enable GitHub Actions workflows** (see #14): `for id in 243664542 243664544 ...; do gh workflow enable $id; done`. The workflows themselves are wired and just disabled.

## Publishing Python packages to PyPI

For each `data-pipeline-*` directory under `data-pipeline-libraries/`:

```bash
cd data-pipeline-libraries/<package>
python3 -m pip install --upgrade build twine
python3 -m build  # produces dist/*.whl and dist/*.tar.gz
python3 -m twine upload --repository pypi dist/*
```

Order matters because of inter-package dependencies:

1. `data-pipeline-core` (no deps inside the framework)
2. `data-pipeline-contract-tests` (depends on core)
3. `data-pipeline-tester` (depends on core)
4. `data-pipeline-gcp-bigquery`, `data-pipeline-gcp-gcs`, `data-pipeline-gcp-pubsub` (depend on core)
5. `data-pipeline-transform`, `data-pipeline-framework`, `data-pipeline-orchestration` (renamed legacy)
6. The deprecation-shim `gcp-pipeline-*` distributions (depend on renamed packages)

## Publishing Java artefacts to Maven Central

From `data-pipeline-libraries-java/`:

```bash
# Validates GPG + Sonatype credentials before deploying.
mvn -P release clean deploy
```

The `release` profile is already configured in the parent POM:
- Signs all artefacts with GPG.
- Uploads via `central-publishing-maven-plugin` to the central staging repo.
- `autoPublish=false` means a manual close+release step at https://central.sonatype.com/ after upload completes.

To publish a single module:

```bash
mvn -P release -pl data-pipeline-gcp-bigquery-java -am clean deploy
```

## Versioning

Currently all artefacts are version `0.1.0`. Bumps happen via:

- **Java:** `mvn versions:set -DnewVersion=0.2.0 -DgenerateBackupPoms=false` from `data-pipeline-libraries-java/`. Commit and push before deploy.
- **Python:** Edit each `pyproject.toml`'s `version = "..."`. Or use `bumpver` / `hatch version` if you adopt one.

The two languages currently version in lockstep; that may change post-1.0.

## Post-release checklist

- Tag the release: `git tag v0.1.0 && git push --tags`.
- Update [CHANGELOG.md](CHANGELOG.md) to move the `[0.1.0] — unreleased` heading to a dated release.
- Announce: GitHub release notes, blog post, book chapter linking the published artefacts.

## What CANNOT be automated until the rename happens

Maven artefact `groupId` is `com.enrichmeai.culvert` — that's stable. PyPI package names are `data-pipeline-*` — also stable. The GitHub repo name `gcp-pipeline-reference` is misleading post-Stage-2; see [REPO_RENAME.md](REPO_RENAME.md). The repo rename does NOT block publishing.
