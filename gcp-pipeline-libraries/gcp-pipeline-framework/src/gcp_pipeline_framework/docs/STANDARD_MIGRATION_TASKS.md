# Standard Migration Tasks & Ticket Templates

This guide provides a standardized breakdown of major tasks required to onboard a new pipeline system using the framework. Use these tasks to create Jira tickets or project plans.

---

## Task Hierarchy

A standard system migration is broken down into **5 Work Streams**, corresponding to the 3-Unit Deployment model plus initial analysis and infrastructure.

### Work Stream 1: Analysis & Schema Definition
*Focus: Defining the contract between the source system and GCP.*

1.  **Analyse Source Extract**: Identify HDR/TRL format, delimiters, and file naming conventions.
2.  **Define Entity Schema**: Create `EntitySchema` definitions in `gcp-pipeline-core` including data types, nullability, and regex patterns.
3.  **Map ODP to FDP**: Document the transformation logic (joins, filters, business rules) from raw tables to business-ready tables.
4.  **Identify PII/Sensitive Data**: List columns requiring masking or hashing in the FDP layer.

### Work Stream 2: Infrastructure (Terraform)
*Focus: Provisioning the "house" for the data.*

1.  **Create System Folders**: Set up new Terraform modules under `infrastructure/terraform/systems/<system_id>/`.
2.  **Provision GCS Buckets**: Create Landing, Archive, Error, and Temp buckets with env suffix (`{PROJECT_ID}-{system_id}-{env}-landing`).
3.  **Provision BigQuery Datasets**: Create `odp_<system_id>` and `fdp_<system_id>` datasets.
4.  **Configure Pub/Sub**: Create file notification topics and subscriptions.
5.  **IAM Role Assignment**: Provision dedicated Service Accounts for Ingestion, Transformation, and Orchestration with least-privilege roles.

### Work Stream 3: Ingestion Unit (Unit 1 — Beam/Dataflow)
*Focus: Moving data from GCS to BigQuery ODP.*

1.  **Initialise Ingestion Project**: Create `deployments/<system_id>-ingestion/` structure.
2.  **Implement File Validation**: Configure `HDRTRLParser` for the system's specific header/trailer format.
3.  **Create Beam Pipeline**: Implement the pipeline using `BasePipeline` (recommended) or `beam.Pipeline`, ensuring `SchemaValidateRecordDoFn` and audit columns are included.
4.  **Configure Flex Template**: Build the Docker image and JSON metadata for the Dataflow Flex Template.
5.  **Unit Testing**: Achieve >80% coverage on custom transforms and validators.

### Work Stream 4: Transformation Unit (Unit 2 — dbt)
*Focus: Transforming data from ODP to FDP.*

1.  **Initialise dbt Project**: Create `deployments/<system_id>-transformation/dbt/`.
2.  **Implement Staging Models**: Create 1:1 staging views with basic casting and renaming.
3.  **Implement FDP Models**: Write the SQL logic for the final business-ready tables.
4.  **Apply Audit Macros**: Ensure all models use the `add_audit_columns()` macro from `gcp-pipeline-transform`.
5.  **PII Masking**: Apply masking macros to sensitive columns identified in the analysis phase.

### Work Stream 5: Orchestration Unit (Unit 3 — Airflow)
*Focus: Coordinating the event-driven flow.*

1.  **Initialise Orchestration Project**: Create `deployments/<system_id>-orchestration/dags/`.
2.  **Implement Trigger DAG**: Configure the `BasePubSubPullSensor` to listen for `.ok` files.
3.  **Implement Load DAG**: Use `BatchDataflowOperator` (from library) or standard `DataflowStartFlexTemplateOperator` to launch the Ingestion unit.
4.  **Implement Transform DAG**: Use `BashOperator` to execute `dbt run` for the Transformation unit.
5.  **Implement Dependency Logic**: (If applicable) Configure `EntityDependencyChecker` for multi-entity JOIN patterns.

---

## Standard Ticket Templates

### Ticket T1: Ingestion Onboarding (System: [ID])
**Description:** Implement the Unit 1 (Ingestion) deployment to move [Entity Name] from GCS to ODP.
**Definition of Done:**
- [ ] Schema defined in `schema.py`.
- [ ] Beam pipeline successfully loads sample file to BigQuery.
- [ ] HDR/TRL validation passes.
- [ ] Audit columns (`_run_id`, `_processed_at`) are present in ODP.
- [ ] Unit tests passing.

### Ticket T2: Transformation Implementation (System: [ID])
**Description:** Implement Unit 2 (Transformation) to create the FDP table [Table Name].
**Definition of Done:**
- [ ] Staging models created.
- [ ] FDP SQL logic implements all business rules.
- [ ] `dbt test` passes (unique, not_null checks).
- [ ] PII data is masked according to policy.
- [ ] Audit columns correctly propagated from ODP.

### Ticket T3: Orchestration Setup (System: [ID])
**Description:** Implement Unit 3 (Orchestration) to automate the flow from file arrival to FDP load.
**Definition of Done:**
- [ ] Trigger DAG successfully senses `.ok` file.
- [ ] Load DAG triggers and monitors Dataflow job.
- [ ] Transform DAG triggers dbt run upon ingestion success.
- [ ] (If multi-entity) Dependency checker correctly waits for all entities.
- [ ] Error notification (Slack/Email) configured for failures.

---

## Migration Checklist (Go-Live)

1.  [ ] **Dry Run**: Upload sample files to Dev Landing bucket and verify full E2E flow.
2.  [ ] **Performance Check**: Verify Dataflow worker scaling for production-sized files.
3.  [ ] **Reconciliation Check**: Run a manual query to verify BQ record counts match TRL counts.
4.  [ ] **Security Audit**: Verify Service Account keys are managed in Secret Manager and not hardcoded.
5.  [ ] **Monitoring**: Ensure system dashboard shows active runs and error rates.
