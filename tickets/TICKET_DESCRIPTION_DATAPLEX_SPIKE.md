# JIRA TICKET: CORE-DQ-006 | Spike: Dataplex Auto DQ Investigation & Reusable Configuration Patterns

## 📋 Summary
Technical investigation (Spike) to evaluate **Google Cloud Dataplex Auto DQ** as a standalone capability for data quality validation. The goal is to determine feasibility, define reusable configuration patterns, and establish a "gold standard" for managed DQ scans that could eventually be integrated into broader automation if successful.

---

## 📖 Description
**As a** Data Platform Architect,  
**I want** to conduct a dedicated spike into Dataplex Auto DQ features,  
**So that** we can understand how to define data quality rules as reusable configuration (YAML/Terraform) and decide if this managed service meets our enterprise requirements for scale and flexibility.

**Note:** This investigation is focused on the standalone capabilities of the service. While the ultimate goal is modularity, this spike should be executed with a "Discovery First" mindset—verifying if the service can handle our use cases before any library-specific implementation is considered.

### 🎯 Business Value
- **Service Validation**: Confirm if Dataplex can replace or augment existing manual/custom validation processes with a managed GCP service.
- **Config-as-Code**: Explore how DQ rules can be version-controlled and deployed using standard CI/CD patterns (YAML definitions).
- **Informed Decision Making**: Provide a clear "Go/No-Go" recommendation for broader adoption based on actual spike results.
- **Reusable Patterns**: Establish baseline templates (Terraform for infrastructure, YAML for rules) that can be shared across teams.

---

## ✅ Acceptance Criteria

### Phase 1: Exploration & Setup
- [ ] **Environment Provisioning**: Create a sandbox Dataplex Lake, Zone, and Asset (BigQuery/GCS) via Terraform or Console.
- [ ] **Basic Rule Execution**: Successfully run a "Critical 5" DQ scan (Null checks, Uniqueness, Range) using a YAML configuration file.
- [ ] **Custom SQL Rules**: Test the implementation of complex business logic using Dataplex's Custom SQL rule type.

### Phase 2: Reusability & Scaling
- [ ] **Parameterization Study**: Investigate how to reuse a single YAML rule set across multiple tables/assets.
- [ ] **Integration Patterns**: Explore how to trigger scans via CLI/API and how to retrieve results programmatically.
- [ ] **Reporting & Dashboards**: Evaluate the built-in Dataplex DQ dashboards and export results to BigQuery for custom reporting.

### Phase 3: Evaluation & Recommendation
- [ ] **Cost/Performance Matrix**: Document execution times and associated BigQuery/Dataplex costs for various dataset sizes.
- [ ] **Security & Governance**: Verify how IAM roles and VPC-SC perimeters affect scan execution and result visibility.
- [ ] **Final Report**: A "Spike Success" document outlining whether we should move forward with building this into a centralized library.

---

## 🛠 Technical Things to Try Out

### 1. Reusable YAML Configuration
Evaluate the following structure for rule definitions:
```yaml
# Example: reusable_rules.yaml
rules:
  - column: account_id
    dimension: Validity
    kind: NOT_NULL
  - column: transaction_amount
    dimension: Validity
    kind: RANGE_CHECK
    params:
      min_value: 0
```

### 2. Standalone Triggering (No Library)
Test triggering via gcloud command line to simulate automation:
```bash
gcloud dataplex data-scans create data-quality ... --data-quality-spec=rules.yaml
```

### 3. Terraform Module Pattern
Develop a prototype Terraform module that provisions the DataScan resource alongside the target BigQuery table.

---

## 📋 Sub-Tasks
- [ ] **Setup**: Provision GCP resources for the spike.
- [ ] **Testing**: Execute standard and custom SQL rules against a representative dataset.
- [ ] **Investigation**: Document the process for multi-asset rule application (reusability).
- [ ] **Analytics**: Export DQ results to a BigQuery dataset and create a sample Data Studio/Looker view.
- [ ] **Review**: Present findings to the architecture board for "Go/No-Go" decision.

---

## 📚 References
- **GCP Docs**: [Dataplex Data Quality Overview](https://cloud.google.com/dataplex/docs/data-quality-overview)
- **Rule YAML Spec**: [Data Quality YAML Specification](https://cloud.google.com/dataplex/docs/data-quality-yaml-spec)
