# Architectural Guide: Pub/Sub vs. Cloud Run in Migration "paved paths"

## 1. Overview
This document clarifies the roles of Google Cloud Pub/Sub and Cloud Run within the migration framework's "paved path" architecture. It specifically addresses how these components handle event detection, execution, and retries.

## 2. Component Comparison

| Feature | Cloud Run | Pub/Sub |
| :--- | :--- | :--- |
| **Primary Role** | **Execution**: Hosts logic like dbt transformations or custom processing scripts. | **Transport**: Buffers and delivers event notifications (e.g., GCS file arrivals). |
| **Activation Pattern** | **Passive/Synchronous**: Sits idle until an external request (HTTP) is received. | **Active/Asynchronous**: Broadcasts a message to subscribers as soon as an event occurs. |
| **State & Resilience** | **Stateless**: Processes the request and exits. No built-in message memory. | **Durable**: Retains messages in a subscription until they are successfully acknowledged. |
| **Typical Usage** | Unit 2 (Transformation) | Unit 3 (Orchestration) Triggering |

## 3. The Layered Retry Strategy
The framework ensures high availability and data integrity by implementing retries at three distinct levels:

### Level 1: Trigger Reliability (Pub/Sub)
*   **What it covers**: The communication between GCS and the Orchestration Unit.
*   **Mechanism**: If the `BasePubSubPullSensor` in Airflow fails to process a message (due to a transient error), the message is **not acknowledged**. Pub/Sub will redeliver it after the "ack deadline" expires.
*   **Outcome**: No file notification is ever lost, even if the Airflow environment is temporarily down.

### Level 2: Orchestration Reliability (Airflow/Composer)
*   **What it covers**: The execution of the Ingestion (Dataflow) and Transformation (Cloud Run) jobs.
*   **Mechanism**: Airflow uses standard `retries` and `retry_delay` parameters for its tasks.
*   **Outcome**: If a Cloud Run job fails due to a network timeout or resource issue, Airflow automatically triggers a retry of that specific step without human intervention.

### Level 3: Execution Reliability (Dataflow / Cloud Run)
*   **What it covers**: Internal processing logic.
*   **Mechanism**: 
    - **Dataflow**: Automatically retries worker-level failures and handles autoscaling.
    - **Cloud Run**: Can be configured with its own internal retry logic or relies on the caller (Airflow) to restart the request.

## 4. Re-run Strategy & Idempotency
A "paved path" re-run should always be initiated via **Airflow**, not by calling Cloud Run directly.

*   **Idempotency (The `run_id` Contract)**: Every run is associated with a unique `run_id`. All transformation logic (dbt) and ingestion logic are designed to be idempotent.
*   **Safe Re-runs**: Re-running a task with the same `run_id` will safely overwrite previous results in BigQuery, preventing data duplication.
*   **Audit Consistency**: Triggering via Airflow ensures the `job_control` table and `AuditTrail` remain synchronized, providing a complete "paper trail" for compliance.

## 5. Summary
Pub/Sub provides the **resilient handshake** that detects data arrival. Cloud Run provides the **scalable engine** that performs the transformation. Airflow acts as the **conductor** that coordinates their retries and maintains the unified state of the migration.
