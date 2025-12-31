# JIRA TICKET: CORE-DQ-003 | Implement Dataplex DQ Orchestrator & Library Integration

## 📋 Summary
Develop the components to programmatically interface with Google Cloud Dataplex for Data Quality (DQ) operations and integrate them into the `gdw_data_core` library as an optional, high-performance alternative to existing checkers.

---

## 📖 Description
**As a** Pipeline Engineer,  
**I want** a standardized client within the `gdw_data_core` library to trigger, monitor, and retrieve results from Dataplex DQ scans,  
**So that** I can leverage managed infrastructure for quality enforcement while maintaining compatibility with our existing pipeline patterns.

### 🎯 Business Value
- **Reduced Maintenance**: Leverages Google's managed Spark engine for DQ alongside our custom code.
- **Consistency**: Provides a unified entry point in the library for both legacy and Dataplex-backed quality reporting.
- **Scalability**: Decouples DQ execution from the pipeline's compute resources for large datasets.
- **Hybrid Support**: Allows teams to choose the best engine for their specific data quality needs.

---

## ✅ Acceptance Criteria
- [ ] **DataplexDQClient**: A new client wrapper for the `google-cloud-dataplex` SDK within `gdw_data_core`.
- [ ] **Trigger Mechanism**: Ability to trigger a Dataplex Data Quality scan for a specific BigQuery or GCS asset.
- [ ] **Polling & Wait**: Implementation of a polling mechanism to wait for scan completion with configurable timeouts.
- [ ] **Result Extraction**: Method to fetch the latest DQ scan results and map them to a standardized `QualityCheckResult` object (same as existing checkers).
- [ ] **Error Handling**: Robust handling of Dataplex API errors, task failures, and timeout scenarios.
- [ ] **Library Integration**: A new `DataplexChecker` class in `gdw_data_core.core.data_quality` that adheres to the library's existing checker interface.

---

## 🛠 Technical Implementation Details

### Proposed Architecture
1. **`DataplexDQClient`**: Lower-level wrapper for GCP API calls.
2. **`DataplexDQOrchestrator`**: Higher-level service that coordinates the "Trigger -> Wait -> Fetch -> Report" workflow.
3. **`DataplexChecker`**: A library-compliant checker that enables one-liner integration: `checker.check_via_dataplex(asset_id="...")`.

### Standardized Interface
```python
from gdw_data_core.core.data_quality import DataQualityChecker

checker = DataQualityChecker(entity_type="loan")
# New Dataplex-backed check
result = checker.check_via_dataplex(
    asset_id="loan_applications",
    wait_for_completion=True
)
print(f"Dataplex Quality Score: {result.score}")
```

---

## 📋 Sub-Tasks
- [ ] Implement `DataplexDQClient` using `google-cloud-dataplex`.
- [ ] Implement `DataplexDQOrchestrator` with sync/async execution modes.
- [ ] Add unit tests for the orchestrator using Mocks for the Dataplex API.
- [ ] Add `DataplexChecker` to `gdw_data_core/core/data_quality/`.
- [ ] Update `DataQualityChecker` to include the `check_via_dataplex` method.

---

## 📚 References
- **Investigation Ticket**: `tickets/TICKET_DESCRIPTION_DATAPLEX_INVESTIGATION.md` (CORE-DQ-002)
- **Official Docs**: [Google Cloud Dataplex Auto DQ](https://cloud.google.com/dataplex/docs/data-quality-overview)
