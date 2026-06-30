# Appendix D — Glossary

- **Adapter** — A cloud- or technology-specific implementation of a Culvert contract. For example, `GcsBlobStore` is the GCP adapter for the `BlobStore` contract. Adapters live in technology-specific modules (e.g. `data-pipeline-gcp-gcs`) and are discovered at runtime via auto-config.\index{adapter}

- **Auto-config / discovery** — The mechanism by which Culvert finds installed adapters without hardcoded wiring. In Java, `AutoConfig.discover()` uses the standard `ServiceLoader` mechanism; in Python, the equivalent uses package entry-points. Adding a new adapter module to the classpath or environment is sufficient — no manual registration required.\index{auto-config}

- **CDP** — Consumable Data Product. Narrow, contracted views derived from FDP for downstream consumers.\index{CDP}

- **Contract** — A language-neutral interface (Java interface or Python Protocol) that every adapter for a given capability must implement. Contracts live in `data-pipeline-core-java` and `data-pipeline-core` and are the stable boundary that makes adapters interchangeable.\index{contract}

- **Coordinated release** — The discipline of publishing the Java artefacts (Maven Central) and the Python package (PyPI `culvert`) together, gated on both passing their respective test suites. A Java-only or Python-only release is considered incomplete.\index{coordinated release}

- **DLQ** — Dead-Letter Queue. Pub/Sub destination for messages that fail to deliver.\index{DLQ}

- **FDP** — Foundation Data Product. The clean, business-shaped layer of BigQuery built from ODP.\index{FDP}

- **Flex Template** — A Dataflow packaging format where the pipeline is a Docker image launched with parameters.\index{Flex Template}

- **HDR/TRL** — Header/Trailer envelope on a mainframe extract file.\index{HDR/TRL}

- **JOIN pattern** — A transformation that combines multiple ODP sources into one FDP table.\index{JOIN pattern}

- **MAP pattern** — A transformation that maps one ODP source to one FDP table.\index{MAP pattern}

- **ODP** — Original Data Product. The untransformed BigQuery layer that mirrors mainframe extracts.\index{ODP}

- **OTEL** — OpenTelemetry. Vendor-neutral observability framework.\index{OTEL}

- **PII** — Personally Identifiable Information.\index{PII}

- **Reactor** — The Java Maven multi-module build that composes the Culvert framework modules (core contracts, GCP adapters, AWS skeletons, Azure skeletons, contract-test harnesses) into a single releasable unit.\index{reactor}

- **Reconciliation** — The check that envelope counts, ingested counts, and BigQuery row counts agree.\index{reconciliation}

- **Run ID** — The unique identifier for a single pipeline execution; threaded through every artefact.\index{run ID}

- **System** — A logical grouping of entities sharing infrastructure. The reference implementation has one: `generic`.\index{system}

- **Three-unit deployment model** — the predecessor GCP reference implementation's split of ingestion, transformation, and orchestration into independently versioned, deployed units. Culvert generalises this behind contracts and adapters rather than mandating a fixed unit layout.\index{three-unit deployment model}

- **Unit** — One of the three deployment units within a system.\index{unit}

- **WIF** — Workload Identity Federation. GCP's keyless authentication pattern for external systems (e.g. GitHub).\index{WIF}

\newpage
