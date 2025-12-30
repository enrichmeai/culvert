### Ticket Description: Strategic Framework for Intelligent Routing & Orchestration
**Ticket ID:** LOA-PLAT-001 (Generic Platform Ticket)  
**Status:** Defined  
**Priority:** HIGH  
**Epic:** Epic 4: Messaging & Integration (Platform Foundation)

#### 1. Objective
Develop a standardized, modular framework for event-driven data processing. This ticket focuses on the "Engine" that handles metadata extraction, intelligent routing, and unified processing patterns, ensuring that business logic is decoupled from orchestration. This framework will eventually be externalized into a shared library.

#### 2. Acceptance Criteria
*   **AC 1: Modular Metadata Extraction**
    *   **Given** a Pub/Sub message from a GCS notification
    *   **When** processed by the sensing module
    *   **Then** it must extract a consistent set of metadata (e.g., source, entity, file_type, processing_mode)
    *   **And** inject this metadata into the Airflow workflow context (`loa_metadata`).
*   **AC 2: Config-Driven Routing Engine**
    *   **Given** the extracted metadata
    *   **When** the `PipelineRouter` logic is invoked via a `BranchPythonOperator` (or similar)
    *   **Then** it must determine the correct target pipeline/DAG based on a central configuration (YAML/Dict)
    *   **And** it must support "Fail-Fast" validation (e.g., checking for required columns) before triggering compute resources.
*   **AC 3: Unified Processing Interface**
    *   **Given** the routed task
    *   **When** the Dataflow job is initiated
    *   **Then** the base implementation must support a dual-mode interface (Batch/Streaming)
    *   **And** allow toggling between GCS and Pub/Sub sources without re-writing core transformation logic.

#### 3. Technical Requirements
- **PipelineSelector/Router**: Logic to map file patterns/metadata to specific Task IDs or DAG IDs.
- **Config Layer**: A YAML-based or JSON-based registry of file types, target tables, and schema requirements.
- **Standardized Context**: Use of Airflow XComs or specific variable injection to pass `routing_info` between tasks.
- **Library Readiness**: Code must be written as modular Python classes (e.g., `BasePipelineRouter`, `PipelineConfig`) to facilitate future move to a core library.

#### 4. Definition of Done
- [ ] `PipelineRouter` class implemented and unit-tested.
- [ ] Reference implementation in a "Template DAG" showing the `Sensor -> Router -> Branch` flow.
- [ ] Documentation of the "Routing Standard" for future legacy migrations.
- [ ] 100% test coverage for standalone routing logic.
