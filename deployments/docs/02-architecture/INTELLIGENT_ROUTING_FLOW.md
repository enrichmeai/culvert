# 📊 Intelligent Routing & Orchestration Flow

This document contains the architectural flow for the generic event-driven routing engine. The diagram below uses **Mermaid.js** syntax, which is natively supported by Confluence (via the Mermaid macro) and GitHub.

## 🔄 Architectural Flow Diagram

```mermaid
graph TD
    %% Source Layer
    subgraph "1. Event Source (GCS)"
        A[".ok File Lands in GCS"] -->|OBJECT_FINALIZE| B["GCS Notification"]
    end

    %% Messaging Layer
    subgraph "2. Messaging (Pub/Sub)"
        B -->|Encrypted Message| C["Topic: loa-processing-notifications"]
        C -->|Reliable Delivery| D["Subscription: loa-processing-notifications-sub"]
    end

    %% Orchestration Layer
    subgraph "3. Orchestration (Airflow)"
        D -->|Pulls Message| E["LOAPubSubPullSensor"]
        E -->|Extract Metadata| F["Metadata Extractor"]
        F -->|Inject context: source, entity, mode| G{"PipelineRouter (Config-Driven)"}
        
        %% Routing Decisions
        G -->|Match Found| H["Branching Logic"]
        G -->|Invalid Schema| I["Fail-Fast: Quarantine & Alert"]
        
        H -->|Entity: Applications| J["Trigger: Applications Pipeline"]
        H -->|Entity: Customers| K["Trigger: Customers Pipeline"]
        H -->|Entity: Others| L["Trigger: Generic Pipeline"]
    end

    %% Processing Layer
    subgraph "4. Processing (Dataflow)"
        J -->|Batch Mode| M["BasePipeline (GCS Read)"]
        K -->|Streaming Mode| N["BasePipeline (Pub/Sub Read)"]
    end

    %% Styles
    style G fill:#f9f,stroke:#333,stroke-width:2px
    style I fill:#f66,stroke:#333
    style J fill:#00ff0033,stroke:#333
    style K fill:#00ff0033,stroke:#333
```

## 🧩 Flow Description

1.  **GCS Event**: A control file (`.ok`) lands in the landing bucket, triggering a `google_storage_notification`.
2.  **Messaging**: A CMEK-encrypted message is published to Pub/Sub.
3.  **Sensor & Extraction**: The `LOAPubSubPullSensor` in Airflow picks up the message and extracts metadata (file path, entity type, etc.) into the `loa_metadata` XCom.
4.  **Intelligent Routing**: The `PipelineRouter` reads a YAML configuration and determines the correct target pipeline. It also performs a "pre-flight" check on the file structure.
5.  **Branching**: The `BranchPythonOperator` (or Trigger mechanism) routes the workflow to the specific entity-based Dataflow job.
6.  **Unified Processing**: The `BasePipeline` (from the library) executes the business logic in either Batch or Streaming mode based on the router's decision.

## 📋 Confluence Integration
To add this to Confluence:
1.  Install/Enable the **Mermaid Charts** macro.
2.  Insert the macro into your page.
3.  Copy and paste the Mermaid code block above into the macro editor.
