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

## 🛠 PENDING TASKS & PROMPTS

### 1. SonarQube & Technical Debt Hardening
**Objective**: Resolve technical debt, improve code quality, and ensure the monorepo meets enterprise-grade SonarQube/Qodana standards.

**Scope**:
1. **Type Safety**: Implement comprehensive Python type hinting (`typing` module) across all `libraries/` to improve IDE support and catch static errors.
2. **Documentation**: Ensure 100% Docstring coverage for all public classes and methods using the Google Python Style Guide format.
3. **Security**:
   - Audit all `subprocess` and `os.system` calls for injection risks.
   - Verify that no sensitive GCP keys or project IDs are hardcoded.
4. **Code Smells**:
   - Refactor overly complex methods (Cyclomatic Complexity > 10).
   - Remove any dead code or unused imports identified during the refactoring.
5. **Testing**: Increase branch coverage for edge cases in `gcp-pipeline-core` and `gcp-pipeline-beam`.

**Strict Constraint**: Maintain the "Zero-Bleed" and "Strict Genericity" policies throughout all fixes.

---

### 2. Documentation & README Synchronization
**Objective**: Conduct a final sweep of the Root README and all secondary documentation to ensure 100% accuracy and alignment with the current implementation.

**Scope**:
1. **Root README.md**:
   - Update the "Project Structure" to reflect the finalized 3-unit deployment model.
   - Enhance the "Getting Started" section with a clear path for new developers.
   - Verify all cross-links to sub-library READMEs are functional.
2. **Technical Architecture (TAD)**:
   - Synchronize the TAD with the recent "Strict Genericity" and "Global-First" (UK-ready) refactoring.
   - Update the "Dependency Matrix" to reflect the finalized Zero-Bleed rules.
3. **Deployment Guide**:
   - Verify that the `CREATING_NEW_DEPLOYMENT_GUIDE.md` perfectly matches the finalized `templates/dags/`.
   - Ensure the "JOIN vs SPLIT" pattern documentation is clear and actionable.
   - **Flow Diagrams**: Verify that all flow diagrams in deployment READMEs (EM and LOA) are complete and accurately reflect the library components used (e.g., `HDRTRLParser`, `BasePubSubPullSensor`, `EntityDependencyChecker`).
4. **Harness Configs**:
   - Audit all `harness-ci.yaml` files for consistent placeholder usage (`# UPDATE to your Project ID`).

**Goal**: The documentation must be so clear that a new engineer can deploy a system like `EM` or `LOA` in under 30 minutes using the provided guides and templates.

---

**Status:** Architecture Restructuring Complete ✅ | Prioritizing Production Readiness 🏗️

