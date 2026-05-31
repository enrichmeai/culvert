# GitHub repository rename procedure

The repo was created as `enrichmeai/gcp-pipeline-reference` when the framework was GCP-coupled. After Stage-2 split it's a polyglot, cloud-neutral framework. The repo name is misleading.

**Not automated.** Joseph decides the new name and triggers the rename.

## Suggested names

Pick one. Order = my recommendation, your call.

1. **`culvert-framework`** — matches the brand (Culvert) and the artefact prefix (`data-pipeline-*`). Most discoverable.
2. **`data-pipeline-framework`** — matches the artefact prefix exactly; brand-neutral.
3. **`culvert`** — terse. Risk: too generic on GitHub search.

## Rename steps

1. **Decide.** Update this doc with the chosen name.
2. **Rename on GitHub.** Settings → Repository name → Save. GitHub auto-redirects the old URL.
3. **Update remotes locally:**
   ```bash
   git remote set-url origin git@github.com:enrichmeai/<NEW_NAME>.git
   ```
4. **Update repo references in source.** These files reference `gcp-pipeline-reference` and need rewriting:
   - `data-pipeline-libraries-java/pom.xml` (`<scm>` block, `<url>`)
   - `data-pipeline-libraries-java/*/pom.xml` (per-module)
   - Each `data-pipeline-libraries/*/pyproject.toml` `Homepage`, `Repository`, `Bug Tracker`
   - `CHANGELOG.md`, `README.md`, `RELEASE.md`, this file
   - `docs/framework-evolution/*.md`
   - The book source (when v1 ships)

   Quick find:
   ```bash
   grep -rl "gcp-pipeline-reference" . --include="*.md" --include="*.toml" --include="*.xml"
   ```

5. **Bulk rewrite** (verify with a dry-run diff first):
   ```bash
   grep -rl "gcp-pipeline-reference" . --include="*.md" --include="*.toml" --include="*.xml" \
     | xargs sed -i '' "s/gcp-pipeline-reference/<NEW_NAME>/g"
   ```
6. **Commit and push:**
   ```bash
   git add -A
   git commit -m "chore: rename repo references gcp-pipeline-reference -> <NEW_NAME>"
   git push origin main
   ```
7. **Update Maven Central deployment** (if already published): the `<scm>` block in published POMs cannot be retroactively edited. Future releases pick up the new URL automatically.
8. **Update book v1 references** before publishing the book.

## What this does NOT do

- Change artefact / package names. `com.enrichmeai.culvert:data-pipeline-*` and PyPI `data-pipeline-*` stay the same.
- Change PyPI URLs. `pip install` works against the package name, not the repo.
- Break old git URLs. GitHub redirects `gcp-pipeline-reference` → new name automatically; old clones can still `git pull` until they `git remote set-url`.

## Decision log

| Date | Status | Notes |
|---|---|---|
| 2026-05-26 | Decided to rename eventually; new name TBD by Joseph. | Sprint-1 dev-process locked the Culvert brand + `data-pipeline-*` artefact convention. Repo rename deferred. |
| 2026-05-30 | **Name chosen: `culvert`.** | Joseph's call. GitHub repo renamed `enrichmeai/gcp-pipeline-reference` → `enrichmeai/culvert`; local git remote updated; GitHub auto-redirects the old URL. |
| 2026-05-30 | **Source slug references rewritten.** | `enrichmeai/gcp-pipeline-reference` → `enrichmeai/culvert` across 33 files (POM `<scm>`, pyproject Homepage/Repository/Bug-Tracker, module READMEs, book). Bare `gcp-pipeline-reference` strings in the legacy `gcp-pipeline-libraries/` tree (dir/package names, not the repo) intentionally left unchanged. |
