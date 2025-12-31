# JIRA TICKET: CORE-DQ-RESEARCH | Technical Feasibility & Discovery: Dataplex for Data Quality

## 📋 Summary
Conduct a deep-dive technical investigation into **Google Cloud Dataplex** to determine its suitability as the primary engine for the platform's Data Quality (DQ) and Anomaly Detection. This is a pure research and feasibility task to inform the architectural pivot.

---

## 📖 Description
**As a** Principal Engineer,  
**I want** a comprehensive technical evaluation of Dataplex Auto DQ and Data Profiling,  
**So that** we can validate if managed services can fully replace existing data quality infrastructure without loss of functionality, security, or performance.

### 🎯 Research Objectives
- **Functional Parity**: Can Dataplex native rules (NOT_NULL, UNIQUE, REGEX, etc.) cover all current business validation logic?
- **Advanced Logic Feasibility**: How does Dataplex handle cross-table validation or custom SQL-based quality rules?
- **Performance Analysis**: What is the overhead/latency of running Dataplex scans on large BigQuery datasets?
- **Cost Modeling**: Evaluate the cost of Dataplex managed Spark execution.
- **Security & Compliance**: Validate VPC Service Controls (VPC-SC) compatibility and regional data residency constraints.

---

## ✅ Acceptance Criteria (Research Done)
- [ ] **Technical Gap Analysis**: A detailed document mapping every existing validation check to a Dataplex equivalent (or identifying gaps).
- [ ] **Proof-of-Concept (PoC)**: A successfully executed Dataplex DQ Scan on a production-representative dataset with a shared YAML rule set.
- [ ] **Performance Report**: Benchmarks showing execution time for common scans (e.g., 100M+ records).
- [ ] **Cost Estimate**: A monthly cost projection for enabling Dataplex DQ across all core domains (Loan, Customer, Branch).
- [ ] **Constraint Log**: Documentation of any "hard limits" discovered (e.g., number of rules per asset, supported regions).

---

## 🛠 Investigation Workstreams

### 1. API & Orchestration Research
- Evaluate the `google-cloud-dataplex` Python SDK for triggering and monitoring scans.
- Research how to retrieve granular, record-level failure details from Dataplex output.

### 2. Custom Rule Feasibility
- Test the "Custom SQL" rule type in Dataplex for complex validations that don't fit standard templates.
- Evaluate "Data Profiling" to see if it can replace existing statistical anomaly detection methods.

### 3. Infrastructure Alignment
- Verify if Dataplex requires specific IAM roles or Service Agent permissions that aren't currently provisioned.
- Check integration with Cloud Logging and Monitoring for alerting.

---

## 📋 Sub-Tasks
- [ ] Set up a sandbox Dataplex Lake and Zone for testing.
- [ ] Document the mapping of existing validation logic to Dataplex YAML structures.
- [ ] Run a scale test: Compare DQ scan duration on a 1TB BigQuery table.
- [ ] Perform a security review of the Dataplex service agent permissions.
- [ ] Present findings and "Go/No-Go" recommendation to the Principal Engineer.

---

## 📚 References
- **Official Docs**: [Google Cloud Dataplex Auto DQ](https://cloud.google.com/dataplex/docs/data-quality-overview)
