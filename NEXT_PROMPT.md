# Next Step: E2E Validation and Production Hardening

## Current Goal
The infrastructure and code are ready. The next objective is **End-to-End Validation** on real GCP infrastructure and implementing the **Absolute Must** operational features required for production readiness.

---

## ARCHITECTURAL GOVERNANCE (Zero-Bleed Policy)
You MUST enforce strict separation between functional domains:
1. **The Foundation (`gcp-pipeline-core`)**: NEVER import `beam` or `airflow`.
2. **The Ingestion Layer (`gcp-pipeline-beam`)**: NEVER import `airflow`.
3. **The Control Layer (`gcp-pipeline-orchestration`)**: NEVER import `beam`.
4. **The SQL Layer (`gcp-pipeline-transform`)**: Strictly SQL/Jinja logic. NO Python.
5. **Strict Genericity**: NEVER hardcode project-specific IDs (EM, LOA) in the `libraries/` directory.

---

## 🔴 Absolute Must (Production Readiness)
Critical tasks that must be completed before the platform can be considered "Production Ready".

### 1. E2E Operational Validation (The "Smoke Test")
- [ ] **Run 06_test_pipeline.sh**: Execute the full flow for EM and LOA.
- [ ] **Verify Audit Trail**: Confirm that `run_id` is consistent from the Trigger DAG through Dataflow to the final dbt Transformation.
- [ ] **Job Control Verification**: Ensure the `job_control.pipeline_jobs` table correctly tracks state transitions (PENDING -> RUNNING -> SUCCESS).

### 2. Operational Hardening (Security & Compliance)
- [ ] **Implement `MaskPIIDoFn`**: Create a reusable Beam transform in `gcp-pipeline-beam` that automatically masks fields marked `is_pii=True` in the schema.
- [ ] **Integrate Masking**: Apply this transform to both EM and LOA ingestion pipelines to ensure data privacy in the ODP layer.
- [ ] **Verify Terraform consistency**: Ensure that service account names and IAM permissions match the ones used in deployment CI/CD and Airflow DAGs.

### 3. Cost & Performance Optimization
- [ ] **BigQuery Partitioning**: Update all dbt models to use `extract_date` or `_processed_at` as partition columns.
- [ ] **Clustering**: Identify high-cardinality columns (e.g., `customer_id`) for clustering in FDP tables.

---

## 🔮 Future Enhancements (Post-Go-Live)
Strategic improvements to be tackled after the initial production migration.

- [ ] **Modern Format Support**: Expand `BeamPipelineBuilder` with `read_avro()` and `read_parquet()`.
- [ ] **Metadata-Driven Enrichment Pilot**: Pilot the `apply_enrichment` macro in a real-world scenario.
- [ ] **Dataplex Integration**: Automate sensitive data discovery and policy tagging.
- [ ] **Looker Studio Integration**: Automated dashboarding for pipeline observability.

---

**Status:** Architecture Restructuring Complete ✅ | Prioritizing Production Readiness 🏗️

