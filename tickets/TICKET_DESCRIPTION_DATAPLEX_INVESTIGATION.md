# JIRA TICKET: CORE-DQ-002 | Investigate & Standardize Data Quality via Google Cloud Dataplex

## 📋 Summary
Formally evaluate and transition the platform's Data Quality (DQ) framework to a managed, 
standardized architecture using **Google Cloud Dataplex Auto DQ**.

---

## 📖 Description
**As a** Principal Engineer,  
**I want** to replace our fragmented, manually-coded DQ checks with a managed platform standard,  
**So that** we can reduce maintenance, improve governance, and leverage managed Google Cloud services for data profiling and quality enforcement.

### 🎯 Business Value
- **Platform Standardization**: Evaluate industry-standard YAML-based DQ rules alongside existing library logic.
- **Operational Efficiency**: Explore how managed service configurations can augment or replace complex custom validations.
- **Improved Governance**: Centralize quality reporting and data profiling in the Google Cloud Console while maintaining local auditability.
- **Hybrid Strategy**: Integrate Dataplex into the existing `gdw_data_core` library to provide developers with choice and a phased migration path.

---

## ✅ Acceptance Criteria
- [ ] **Gap Analysis**: Compare current `gdw_data_core` capabilities (Completeness, Uniqueness, Validity, Timeliness) with Dataplex Auto DQ features.
- [ ] **Library Integration Prototyping**: Evaluate how to wrap Dataplex API calls within the `gdw_data_core.core.data_quality` module.
- [ ] **YAML Standard**: Define a standardized YAML template for DQ rules that aligns with library configuration patterns.
- [ ] **Integration Path**: Identify how to trigger Dataplex DQ tasks from our existing orchestration layer (Airflow/Dataflow).
- [ ] **Coexistence Strategy**: Define how legacy DQ results and Dataplex results can be unified in reporting.
- [ ] **Reporting Alignment**: Verify that Dataplex quality scores can be mapped to our enterprise grading (A-F) requirements.

---

## 🛠 Investigation Scope

### 1. Mapping Existing Rules
Current rules to be evaluated for Dataplex parity:
- Completeness -> Dataplex `NOT_NULL`
- Uniqueness -> Dataplex `UNIQUENESS`
- Validity -> Dataplex `REGEX` / `VALUE_SET`
- Footer Count -> Dataplex `ROW_COUNT_EXPECTATION`
- Anomaly Detection -> Dataplex **Data Profiling**

### 2. Implementation Model
- **Managed Assets**: Registering GCS and BigQuery assets in a Dataplex Lake.
- **Library Wrapper**: Developing a `DataplexChecker` that implements the same interface as existing library checkers.
- **Rule Management**: Storing DQ YAMLs in Git and deploying them as Dataplex Tasks.
- **Execution**: Comparing "runtime checks" (library) with "post-load Scans" (Dataplex).

---

## 📋 Sub-Tasks
- [ ] Research Dataplex Auto DQ rule limitations (e.g., custom SQL requirements).
- [ ] Prototype a Dataplex DQ Scan on a sample BigQuery table via the `gdw_data_core` library.
- [ ] Draft the hybrid `DATA_QUALITY_GUIDE.md` (Legacy + Dataplex).
- [ ] Identify integration points for the new `DataplexDQOrchestrator` in existing pipelines.

---

## 📚 References
- **Dataplex Documentation**: [GCP Dataplex Auto DQ](https://cloud.google.com/dataplex/docs/data-quality-overview)
