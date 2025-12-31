# JIRA TICKET: CORE-DQ-005 | Dataplex Integration: Research, Implementation & Hybrid Strategy

## 📋 Summary
Consolidated initiative to evaluate, implement, and integrate **Google Cloud Dataplex Auto DQ** into the `gdw_data_core` library. This ticket covers the full lifecycle from technical feasibility research to the implementation of a permanent hybrid quality strategy where managed services and custom code coexist.

---

## 📖 Description
**As a** Data Platform Team,  
**I want** to integrate Dataplex as a managed, high-performance capability alongside our current custom DQ checks,  
**So that** we can leverage the best tool for each specific data quality requirement (e.g., managed Spark for scale, custom Python for business logic).

### 🎯 Business Value
- **Capability Expansion**: Add industry-standard YAML-based managed DQ rules to our existing custom validation library.
- **Operational Scalability**: Leverage Google's managed Spark engine for DQ scans on large-scale datasets, reducing local compute pressure.
- **Enhanced Governance**: Centralize quality metrics and data profiling in the GCP Console while maintaining local auditability.
- **Hybrid Flexibility**: Support a permanent hybrid model where teams can choose between library-based "runtime" checks and Dataplex "post-load" scans.

---

## ✅ Acceptance Criteria

### Phase 1: Research & Discovery
- [ ] **Technical Gap Analysis**: Document mapping of existing `gdw_data_core` rules (Completeness, Uniqueness, etc.) to Dataplex equivalents.
- [ ] **Performance & Cost Report**: Benchmarks for execution time on large datasets and monthly cost projections.
- [ ] **Security Review**: Validation of VPC-SC compatibility and required IAM permissions.

### Phase 2: Core Implementation
- [ ] **DataplexDQClient**: A standardized wrapper for the `google-cloud-dataplex` SDK within the library.
- [ ] **Orchestration Layer**: Implementation of "Trigger -> Wait -> Fetch -> Map" workflow for DQ scans.
- [ ] **Library Integration**: New `DataplexChecker` class that implements the standard library checker interface.

### Phase 3: Hybrid Strategy
- [ ] **Hybrid Pipeline Pattern**: Reference implementations showing coexistence of custom and Dataplex checkers.
- [ ] **Unified Reporting**: Verification that results from both engines are captured in the pipeline audit trail and mapped to enterprise grading (A-F).
- [ ] **Documentation**: Updated `DATA_QUALITY_GUIDE.md` covering the hybrid approach and best practices for engine selection.

---

## 🛠 Technical Implementation Details

### Proposed Interface
```python
from gdw_data_core.core.data_quality import DataQualityChecker

checker = DataQualityChecker(entity_type="loan")

# Option A: Custom Runtime Check (Existing)
result_custom = checker.check_completeness(df)

# Option B: New Dataplex Managed Scan
result_dataplex = checker.check_via_dataplex(
    asset_id="loan_applications",
    wait_for_completion=True
)
```

---

## 📋 Sub-Tasks
- [ ] **Feasibility**: Prototype a Dataplex DQ Scan on a production-representative dataset via YAML.
- [ ] **Development**: Implement `DataplexDQClient` and `DataplexDQOrchestrator` with sync/async modes.
- [ ] **Testing**: Add unit tests using Mocks for Dataplex API and integration tests for result mapping.
- [ ] **Integration**: Update `DataQualityChecker` to include `check_via_dataplex` method.
- [ ] **Governance**: Create/Deploy DQ YAMLs for high-volume data domains.
- [ ] **Docs**: Update the central Quality Guide to document the hybrid capability.

---

## 📚 References
- **Standard**: [GCP Dataplex Auto DQ](https://cloud.google.com/dataplex/docs/data-quality-overview)
