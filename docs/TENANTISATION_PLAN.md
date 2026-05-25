# Tenantisation Plan

The repository currently hard-codes the tenant slug `joseph-antony-aruja` (the reference GCP project ID) in ~30 places. This document scopes the work needed to turn this into a template any consumer can clone and run against their own GCP project.

Nothing in here is speculative — every reference site below was found by grep. The goal is a PR-sized rollout, not a single mega-change.

## 1. Where the tenant slug appears

Grouped by the kind of change required.

### GCP project IDs, buckets, service accounts (hot path)

| File | Line(s) | Current |
| --- | --- | --- |
| `infrastructure/k8s/workloads/serviceaccount.yaml` | 10 | `airflow-sa@joseph-antony-aruja.iam.gserviceaccount.com` |
| `infrastructure/k8s/airflow/values.yaml` | 79, 93, 112, 121 | bucket `joseph-antony-aruja-airflow-dags`, env `GCP_PROJECT_ID` |
| `infrastructure/k8s/airflow/values-simple.yaml` | 77, 91, 110, 119 | duplicate of above |
| `scripts/gcp/setup_cdp_segment_infra.sh` | 16 | `PROJECT_ID="${1:-joseph-antony-aruja}"` |
| `scripts/gcp/teardown_cdp_segment_infra.sh` | 17, 19 | default + force flag |
| `scripts/gcp/cleanup_builds.sh` | 12 | `PROJECT_ID="joseph-antony-aruja"` (no env fallback) |
| `scripts/gcp/cleanup_stale_resources.sh` | 12 | hard-coded |
| `scripts/gcp/test_generic_e2e.sh` | 7 | hard-coded |
| `scripts/gcp/e2e_pipeline_test.sh` | 25 | `${PROJECT_ID:-joseph-antony-aruja}` |
| `scripts/gcp/deploy_dags_and_test.sh` | 20 | `${PROJECT_ID:-joseph-antony-aruja}` |

### Terraform

| File | Line(s) | Current |
| --- | --- | --- |
| `infrastructure/terraform/systems/segment/main.tf` | 11, 12 | example comment with `-var="gcp_project_id=joseph-antony-aruja"` |

The `env/*.tfvars` files themselves do **not** contain the slug — they take it via `-var`.

### Python

| File | Line(s) | Current |
| --- | --- | --- |
| `scripts/fix_test_data.py` | 14 | `LANDING_BUCKET = "gs://joseph-antony-aruja-generic-int-landing"` |
| `gcp-pipeline-libraries/gcp-pipeline-orchestration/tests/unit/factories/test_dag_factory_parse_message.py` | 347–369 | bucket name in fixture payloads & assertions |

### Documentation (cold path)

Seventeen markdown files under `docs/`, `deployments/*/README.md`, `PROJECT_CONTEXT.md`, and `AUDIT.md` use the slug in `export` examples. These are easy find-and-replace.

## 2. What's already parameterised

The good news: most of the codebase already reads `GCP_PROJECT_ID` or `PROJECT_ID` from the environment.

- `deployments/fdp-trigger/config.py` reads `GCP_PROJECT` from env, no hard-coded default.
- `deployments/fdp-to-consumable-product/dbt/profiles.yml` uses `{{ env_var('GCP_PROJECT_ID') }}` with a `'dummy-project'` fallback for offline compile.
- Most shell scripts use the `${PROJECT_ID:-joseph-antony-aruja}` pattern — the env var wins if set.

So the *mechanism* is already there; the cleanup is removing the hard-coded default from the fallback.

## 3. Recommended variable strategy

**Use `GCP_PROJECT_ID` as a single env var across Terraform, dbt, Python, and shell. Provide `.tfvars.example` / `values.yaml.example` with placeholders. No new config file.**

Rationale: the repo already uses `GCP_PROJECT_ID` and `PROJECT_ID` in most places. Adding a `tenant.yml` or switching to Terraform workspaces would introduce a new concept for no gain. The simplest migration is "strip the default, add an example file, document the env var".

Downside to call out: env vars are global, so in a multi-tenant dev environment you need to be careful about which `GCP_PROJECT_ID` is loaded. That's why we *also* keep the Terraform `-var` override path and the dbt `env_var()` fallback for offline compile.

## 4. PR-sized rollout

Each step is independently shippable — if PR 3 gets blocked on review, PRs 4–8 are still safe to merge.

1. **Shell scripts — standardise env var name and remove hard-coded defaults.**
   Change `PROJECT_ID` to `GCP_PROJECT_ID` in every `scripts/gcp/*.sh`. Replace hard-coded strings with `${GCP_PROJECT_ID:?must be set}` so the script fails loudly when unset. Add a "Required env vars" section to each script's header comment.

2. **Terraform — add `.tfvars.example`, remove inline comments.**
   Drop the `joseph-antony-aruja` example from `main.tf` comments. Add `infrastructure/terraform/systems/segment/env/int.tfvars.example` with `gcp_project_id = "YOUR_PROJECT_ID"`. Update `DEPLOYMENT_OPERATIONS_GUIDE.md` to show `-var-file=env/int.tfvars -var="gcp_project_id=$GCP_PROJECT_ID"`.

3. **Kubernetes / Helm — parameterise `values.yaml`.**
   Replace hard-coded `GCP_PROJECT_ID: joseph-antony-aruja` and bucket names in `infrastructure/k8s/airflow/values*.yaml` with Helm variables (`{{ .Values.gcp.projectId }}`). Add `values.yaml.example`. Update the Airflow init script template to read from the injected env.

4. **Test fixtures — factory-based bucket names.**
   In `tests/unit/factories/test_dag_factory_parse_message.py`, move the hard-coded bucket into a pytest fixture (`@pytest.fixture def project_id(monkeypatch): monkeypatch.setenv("GCP_PROJECT_ID", "test-project"); return "test-project"`). Build payloads from the fixture. Also update `scripts/fix_test_data.py` to read the bucket from env.

5. **Docs sweep — env-var examples everywhere.**
   Update every `*.md` that shows `export PROJECT_ID=joseph-antony-aruja` to `export GCP_PROJECT_ID=<your-project>`. Add a short *Tenantisation* section to `PROJECT_CONTEXT.md` so new readers know the pattern up front.

6. **Service-level audit — fdp-trigger and neighbours.**
   Verify `deployments/fdp-trigger/config.py` has no hidden hard-coded fallbacks. Add a `.env.example` documenting `GCP_PROJECT_ID`, `TEMPLATE_GCS_PATH`, etc. Do the same for `deployments/original-data-to-bigqueryload` and the other services.

7. **CI / GitHub Actions — inject at runtime.**
   Grep `.github/workflows/*.yml` for any residual tenant strings. Where they exist, replace with repo secrets (`${{ secrets.GCP_PROJECT_ID }}`) or workflow env blocks. Add a README note on which secrets consumers must configure.

8. **Embedded framework — re-run the sweep.**
   `gcp-pipeline-libraries/gcp-pipeline-framework/src/gcp_pipeline_framework/deployments/` contains reconstructed copies of several deployments. Run steps 1–7 against that directory too so a release bundle doesn't silently re-introduce the tenant slug.

## 5. Definition of done

After PR 8 merges, the following greps should return zero hits outside `docs/TENANTISATION_PLAN.md` itself and `AUDIT.md`:

```
grep -r "joseph-antony-aruja" . --exclude-dir=.git --exclude-dir=venv --exclude-dir=__pycache__
grep -r "joseph_antony_aruja" . --exclude-dir=.git --exclude-dir=venv --exclude-dir=__pycache__
```

A fresh clone on another GCP project should be able to: set `GCP_PROJECT_ID`, run `terraform apply -var-file=env/int.tfvars`, and have Airflow / Dataflow jobs target the new project without touching any source file.
