# Project rules for Claude / Copilot agents

## Deploy & cost rules (NON-NEGOTIABLE)

1. **Never push to main without explicit deploy intent.**
   - Default commits do NOT trigger GitHub Actions deploys.
   - To deploy, the commit message must contain one of:
     - `[deploy]` → runs deploy workflows (deploy-generic, deploy-orchestration)
     - `[publish:deploy]` → publishes libraries to PyPI then deploys
   - Anything else (docs, refactors, tests, infra plans) commits cleanly with no Actions run.
   - Gate is enforced in `.github/workflows/deploy-generic.yml` and `.github/workflows/deploy-orchestration.yml`.

2. **Composer is opt-in only.** Costs ~$300-500/month.
   - Default: `enable_composer = false` in `infrastructure/terraform/systems/generic/variables.tf`.
   - Never set `enable_composer=true` or pass `deploy_composer=true` without an explicit user request.

3. **Run `/finops-estimate` before any expensive GCP operation.**
   Triggers: `terraform apply`, `gcloud dataflow flex-template run`, Composer/GKE/Cloud Run deploys, E2E test scripts.
   Show a cost breakdown and get explicit approval before proceeding.

4. **Never run `gh workflow run` or trigger GitHub Actions** on the user's behalf unless explicitly asked.

5. **Always tear down after testing.**
   Use `scripts/gcp/00_full_reset.sh --force` (preserves the `github-actions-deploy` SA).
   Remind the user after creating any persistent resource.

6. **Use existing repo scripts** (`00_full_reset.sh`, `cleanup_builds.sh`, `e2e_pipeline_test.sh`) instead of inline `gcloud` commands.

7. **Verify before committing.** Run the `pre-commit-verify` skill: confirm files exist, imports resolve, tests pass. Never push hallucinated code.

## How to deploy

```bash
# Deploy current changes
git commit -m "feat: ... [deploy]"
git push

# Publish libraries + deploy
git commit -m "feat: ... [publish:deploy]"
git push

# Manual trigger (also works)
gh workflow run deploy-generic.yml
```

## How to deploy Composer (rare)

```bash
gh workflow run deploy-generic.yml -f deploy_composer=true
# Then immediately schedule teardown after testing.
```
