# 📊 Generic Blueprint - Data Quality Standards (Hybrid Library & Dataplex)

**Version:** 2.1  
**Last Updated:** December 31, 2025  
**Status:** Multi-Engine Standard

---

## 🎯 Overview

The platform utilizes a **hybrid data quality strategy** to ensure data trust. We combine the fine-grained control of our internal **`gcp_pipeline_core` Python library** with the managed scale and profiling capabilities of **Google Cloud Dataplex**.

### Strategy Goals
✅ **Developer Choice**: Use the library for runtime business logic; use Dataplex for post-load scale.
✅ **Unified Governance**: Aggregate results from both engines into the central audit trail.
✅ **Automated Profiling**: Leverage Dataplex for statistical trends without manual code.
✅ **Extensibility**: Add new Dataplex rules without modifying core library code.

---

## 🛠 Quality Engines

### 1. Library-Based Checks (`gcp_pipeline_core`)
Best for: Low-latency, fine-grained business rules, and runtime validation during data processing.

- **Implementation**: `DataQualityChecker.py`
- **Capabilities**: Completeness, Validity (Regex), Accuracy (Footer Count), Uniqueness, Timeliness.
- **Reporting**: Immediate feedback in pipeline logs and XComs.

### 2. Managed-Service Checks (Dataplex)
Best for: High-volume datasets, complex post-load profiling, and standardized declarative rules.

- **Implementation**: **Dataplex Auto DQ** (YAML-based).
- **Capabilities**: Managed Spark-based scans, ML-based anomaly detection, and centralized Cloud Console dashboards.
- **Reporting**: Results stored in Dataplex Console and published to Cloud Logging.

---

## ✅ Quality Standards (Auto DQ YAML)

When using Dataplex, quality is enforced via standardized YAML rule sets.

### Standard Rule Example (YAML)
```yaml
rules:
  - column: application_id
    dimension: Uniqueness
    threshold: 1.0
  - column: amount
    dimension: Validity
    rule_type: RANGE
    params:
      min: 0
      max: 1000000
```

---

## 🔍 Data Profiling (Dataplex)

Dataplex automatically profiles data to identify statistical trends, distributions, and anomalies.

- **Statistical Analysis**: Automatic calculation of min, max, mean, and quartiles.
- **Drift Detection**: Identification of significant shifts in data distribution over time.

---

## 🛑 Quality Enforcement & Hybrid Orchestration

Pipelines should integrate quality checks using the `gcp_pipeline_core` library wrapper to ensure unified reporting.

### Hybrid Code Example
```python
from gcp_pipeline_core.core.data_quality import DataQualityChecker

checker = DataQualityChecker(entity_type="loan")

# 1. Run library-based business validation
checker.check_completeness(records, required_fields=["app_id"])

# 2. Run Dataplex-managed scan for large-scale quality
checker.check_via_dataplex(asset_id="loan_table")

# 3. Generate unified report
report = checker.get_quality_report()
```

---

## 🎓 Best Practices

### ✅ DO
- Use library-based checks for data that must be validated *before* writing to the warehouse.
- Use Dataplex for periodic "Deep Scans" of large historical datasets.
- Store all DQ YAML files in version control alongside the pipeline code.
- Monitor quality trends via the Dataplex Dashboard.

### ❌ DON'T
- Re-implement standard checks (NOT_NULL, UNIQUE) in custom code if they can be handled by Dataplex.
- Disable existing library checks without verifying functional parity in Dataplex.

---

## 📚 Official Documentation
- [Google Cloud Dataplex Overview](https://cloud.google.com/dataplex/docs/introduction)
- [Dataplex Auto DQ Guide](https://cloud.google.com/dataplex/docs/data-quality-overview)
- [GDW Data Core: Data Quality Module](../gcp-pipeline-libraries/gcp-pipeline-core/src/gcp_pipeline_core/data_quality/)

---

**Last Updated:** December 31, 2025  
**Status:** Production Standard  
**Maintained By:** Platform Engineering Team

