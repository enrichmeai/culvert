# Golden Path Proposal: Standardising Legacy-to-GCP Data Migrations

## 1. Executive Summary

This proposal outlines the transition of our existing data migration framework into an enterprise **Golden Path** for the Credit Platform. By leveraging a **Library-First, 3-Unit Architecture**, we provide a standardised, governed, and low-friction path for migrating legacy mainframe data to GCP BigQuery.

The **Generic reference system** is the centrepiece of this proposal. It is a deliberate combination of what were previously two separate applications — Excess Management and Loan Origination — into a single unified deployment. This design choice is intentional: it demonstrates two distinct pipeline patterns simultaneously, proving that a single shared framework can handle both a complex multi-entity join dependency and a simple single-entity mapping within the same codebase and infrastructure.

---

## 2. What We Have Built (Current State)

### 2.1 The Shared Library Foundation

Enterprise logic has been abstracted into five versioned, reusable libraries published to PyPI under the umbrella package `data-pipeline-framework==1.0.11`:

- `gcp-pipeline-core`: Centralised Audit, Job Control, and FinOps (Cost Tracking). Zero dependencies on Beam or Airflow.
- `gcp-pipeline-beam`: Standardised Ingestion logic — HDR/TRL envelope validation, 25MB+ split-file handling, Dead Letter Queue side outputs.
- `data-pipeline-orchestration`: Airflow DAG Factories, `PubSubPullSensor`, `EntityDependencyChecker` for rapid and consistent scheduling.
- `data-pipeline-transform`: dbt Macros for automated PII masking and audit column injection.
- `data-pipeline-tester`: Mocks, fixtures, and base test classes for consistent pipeline testing.

### 2.2 The 3-Unit Deployment Model

A decoupled architecture that minimises blast radius and optimises cloud costs:

1. **Ingestion Unit** (`original-data-to-bigqueryload`): Dataflow Flex Templates for high-scale processing.
2. **Transformation Unit** (`bigquery-to-mapped-product`): dbt for business-ready Data Products (ODP → FDP).
3. **Orchestration Unit** (`data-pipeline-orchestrator`): Cloud Composer (managed Airflow) for event-driven coordination.

### 2.3 The Generic Reference System: Two Patterns in One

The Generic system consolidates two previously separate applications into a single deployment, demonstrating both patterns the Credit Platform needs to support:

#### JOIN Pattern (from Excess Management)

Multiple entities with staggered extract schedules must all complete before transformation can begin:

- 3 source entities: Customers (4 PM extract), Accounts (4 PM extract), Decision (5 AM extract)
- 3 ODP tables: `odp_generic.customers`, `odp_generic.accounts`, `odp_generic.decision`
- 2 FDP tables: `fdp_generic.event_transaction_excess`, `fdp_generic.portfolio_account_excess`
- Dependency: all 3 entities must reach `SUCCESS` in `job_control` before FDP transformation triggers

This pattern is common across the Credit Platform for any system where a business-ready data product requires joining data from multiple source entities that arrive independently.

#### MAP Pattern (from Loan Origination)

A single entity with a straightforward 1:1 mapping:

- 1 source entity: Applications (daily extract)
- 1 ODP table: `odp_generic.applications`
- 1 FDP table: `fdp_generic.portfolio_account_facility`
- Dependency: transformation triggers immediately after ODP load — no wait required

This pattern covers the majority of simpler migrations where a single mainframe entity maps to a single data product.

### 2.4 Additional Reference Patterns

- **Spanner Transformation (Federated)**: A reference implementation for modern cloud sources using dbt Federated Queries (`EXTERNAL_QUERY`), demonstrating that the 3-Unit model extends beyond mainframe origins.

---

## 3. Why This Should Be the Enterprise Golden Path

### 3.1 Multi-Pattern Coverage

The Generic system proves that a single shared framework handles both the JOIN and MAP patterns — the two most common pipeline shapes on the Credit Platform. Teams do not need to build separate frameworks for simple vs. complex migrations.

### 3.2 Multi-Source Flexibility

The framework supports:
- **Mainframe/Teradata to GCP** via GCS landing + Beam ingestion (proven in production).
- **Cloud Spanner to BigQuery** via two paths: low-friction federated queries for medium data volumes, and high-volume Beam ingestion for enterprise scale.

### 3.3 Production Stability

- Over **780 unit tests** across 5 libraries ensuring the reliability of core migration logic.
- Idempotent pipelines: every run can be safely re-executed with the same `run_id`.
- Dead Letter Queue pattern ensures invalid records never block a pipeline run.

### 3.4 Observability & Compliance by Default

- Built-in integration with Cloud Monitoring and Dynatrace via `gcp-pipeline-core`.
- Every BigQuery row is automatically tagged with `_run_id` and `_source_file` for 100% lineage from mainframe extract to FDP.
- PII masking macros in `data-pipeline-transform` applied at the FDP layer.

### 3.5 Rapid Onboarding

Standardised templates and a "Creating New Deployment" guide allow a new team to deploy a governed pipeline in days, not weeks. The DAGFactory pattern means new entities require only configuration, not new Airflow code.

### 3.6 Future-Proof Modularisation

A clear roadmap towards a "Generic Engine" model — enabling zero-code onboarding via YAML manifests — further reduces the barrier for new teams while ensuring 100% consistent audit and observability standards. See [Modularisation Roadmap](./MODULARIZATION_AND_CONFIG_ROADMAP.md).

---

## 4. Proposed Message to EDP Owner

**Subject:** Proposal: Standardising Legacy-to-GCP Migrations via GCP Pipeline Reference — Golden Path

"Hi [EDP Owner Name],

Following up on your suggestion to take our migration framework to a Golden Path — I have put together a summary of our current production-ready assets and our vision for a 'Generic Engine' platform.

We have successfully abstracted the heavy lifting of legacy migrations — including HDR/TRL validation, split-file handling, real-time monitoring, and FinOps tracking — into a shared-library foundation (published to PyPI as `data-pipeline-framework`). This framework has been proven across two distinct pipeline patterns, which we have consolidated into our **Generic reference system**: the JOIN pattern from Excess Management and the MAP pattern from Loan Origination.

The key differentiator for this Golden Path is our **Modularisation Roadmap**. We are moving towards a Manifest-Driven model where onboarding a new system requires zero new Python code — only a YAML configuration. This will significantly lower the barrier for other Credit Platform teams while ensuring 100% consistent audit and observability standards across the bank.

I would love to show you a 15-minute walkthrough of our **Job Control metadata layer**, the **two-pattern Generic reference system**, and our **Spanner-to-FDP federated implementation**. Do you have any time next week for a brief demo?

Best regards,

[Your Name]"
