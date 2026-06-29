# Chapter 21 — Getting Started and the Roadmap

Culvert is not on Maven Central yet. It is not on PyPI yet. The coordinated 0.1.0 — Java and Python both ready, both published together in a single Joseph-gated release to `com.enrichmeai.culvert:*` and `culvert` respectively — has not shipped at the time I am writing this. I am telling you that upfront so the rest of this chapter is honest rather than aspirational.

What you *can* do right now is build from source, write a pipeline against the contracts, and run the tests. The framework is real; the distribution plumbing is what remains. This chapter is about the former (in three steps, each taking longer than the last) and then the latter (as an honest roadmap, not a marketing slide).

## Fifteen minutes: build from source

Clone the repository and verify you can build both halves:

```bash
git clone https://github.com/enrichmeai/culvert.git
cd culvert
```

**Java** (JDK 17; the Maven toolchain provisions itself):

```bash
mvn -f data-pipeline-libraries-java/pom.xml install
```

That runs unit tests across all thirteen modules in the Java reactor — `data-pipeline-core-java`, the six GCP adapter modules, the two cloud-neutrality skeletons, the orchestration module, and the three test-support modules. Green here means the Java side of the framework compiles and all contract tests pass. (`README.md:55–58`)

**Python** (editable install, so your changes to the library are immediately visible):

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e data-pipeline-libraries/data-pipeline-core pytest
pip install -e data-pipeline-libraries/data-pipeline-gcp-bigquery
pytest data-pipeline-libraries/data-pipeline-core/tests
```

The pattern is the same for any other adapter you need: install the core editable, install the adapter editable alongside it, run its tests. Adapters self-register with `AutoConfig.discover()` via entry-points (`data_pipeline_core.adapters` group in Python; `ServiceLoader` in Java), so you do not wire them together manually. (`README.md:61–69`)

If you only want the cloud-neutral contracts and no GCP adapter — say, to write contract-test mixins or to prototype a new adapter — `pip install -e data-pipeline-libraries/data-pipeline-core` is sufficient. The core has no `google.cloud` imports; that constraint is enforced by a CI grep that fails the build if one leaks in. Everything that touches a real GCP service lives in the named adapter modules and nowhere else.

## An hour: write a pipeline against the contracts

The contracts are defined in `docs/CONTRACT.md` (language-neutral spec) and implemented in `data-pipeline-core-java/.../contracts/` (Java) and `data-pipeline-core/.../contracts/` (Python). There are sixteen of them — `Source`, `Sink`, `Transform`, `Pipeline`, `RuntimeContext`, `BlobStore`, `Warehouse`, `FinOpsSink`, `GovernancePolicy`, `LineageEmitter`, `ObservabilityHook`, `JobControlRepository`, `AuditEventPublisher`, `SecretProvider`, plus `StageMetrics` and `StageMetricsHook` — and the rule for using them is simple: you always write to the contract, never to the adapter.

The concrete path for Java: implement `Source<T>` and `Sink<T>`, wire them through a `Pipeline`, obtain a `RuntimeContext` from `AutoConfig.discover()`, and call `pipeline.run(context)`. The BigQuery warehouse, the GCS blob store, the Pub/Sub audit publisher — all of them arrive via the auto-config discovery at runtime rather than being hardcoded. Your pipeline code never imports `GcsBlobStore` or `BigQueryWarehouse` directly. It asks the runtime for a `BlobStore`, and the `ServiceLoader` machinery hands back the right one.

The concrete path for Python is structurally identical: use the Protocols from `data-pipeline-core/contracts/`, call `AutoConfig.discover()`, and write your business logic against the protocol surface. The adapters in `data-pipeline-gcp-bigquery`, `-gcs`, `-pubsub` register themselves under the entry-point group; the runtime finds them.

The contract-tests module — `data-pipeline-contract-tests*` — is where conformance is enforced. Every adapter must pass those tests; every new adapter you write should bind to them. Chapter 16 covers this in full. The point here is that the test suite tells you whether your adapter is conformant, not whether your adapter works. Those are different questions; the contract tests answer the first one systematically, and your integration tests answer the second.

## A day: run the full integration tests

Once you have the Docker daemon available, the integration tests exercise the full round-trip against real GCP APIs (or local emulators, depending on the test profile):

```bash
mvn -f data-pipeline-libraries-java/pom.xml -P it verify
```

The `it` profile pulls in Testcontainers and runs the `*IT` classes. These are the tests that matter for production confidence; they are deliberately excluded from the default `install` so your edit-compile-test loop stays fast. (`README.md:57`)

The Python equivalents run through the same `pytest` invocation extended to the adapter packages:

```bash
pytest data-pipeline-libraries/data-pipeline-gcp-bigquery/tests
pytest data-pipeline-libraries/data-pipeline-gcp-gcs/tests
```

A day is a pessimistic estimate; the integration tests will likely complete faster once the environment is set up. I say a day because the first time you wire a new GCP project — service accounts, API enablement, IAM bindings — there is genuine friction, and friction absorbs clock time even when the actual work is small. Plan for it.

## The roadmap

The framework is at a specific, honest position: Java built to `0.1.0` (frozen at tag `java-0.1.0`), Python contracts reconciled and core depth done, GCP adapters complete on both sides. The gap is packaging and the publish plumbing. Here is what is left, in sequence. (`docs/framework-evolution/13-python-parity-release.md:1–10`)

**Wave C — adapter parity (done).** The Python `SecretManagerProvider` and the Python `gcp-observability` package (CloudTrace hook, DataCatalog lineage, CloudMonitoring metrics) have landed, along with per-service cost trackers for the Python BigQuery, GCS, and Pub/Sub modules. The gap table in `docs/framework-evolution/13-python-parity-release.md` still shows Wave C as pending — that doc is a pre-Wave-C snapshot and is stale; `README.md:81` is current and marks it done. (`README.md:81`)

**Wave D — packaging and naming.** This is the remaining gate — the wave that produces `culvert` on PyPI. The Python distributions are currently named `data-pipeline-*`; they will be renamed to `culvert-core`, `culvert-gcp-bigquery`, and so on, mirroring the Java module naming. Import shims from the old names will be provided for one release. The open decision is whether to ship a single `culvert` mega-package or `culvert` plus `culvert-gcp-*` extras — the recommendation (and my strong preference) is the split, because it keeps install footprint small and matches the Java story: you only pull in the adapters you actually need. (`docs/framework-evolution/13-python-parity-release.md:107–113`)

**The coordinated release.** The release gate is explicit: Java ready *and* Python ready, then a single publish to Maven Central (`com.enrichmeai.culvert:*`) and PyPI (`culvert`), triggered manually by me. The Java version numbers and the PyPI version numbers will both be `0.1.0`. PyPI version numbers cannot be reused and Maven Central is immutable; the publish is irreversible, which is precisely why it stays Joseph-gated rather than automatic. (`docs/framework-evolution/13-python-parity-release.md:34–48`)

**AWS and Azure.** The Java reactor already contains `data-pipeline-aws-s3-java` and `data-pipeline-azure-blob-java` as skeletons — they compile, they define the module structure, they prove the contract seam is real. They are not production implementations. Python cloud-neutral skeletons for AWS and Azure are out of scope for the 0.1.0 coordinated release; they are explicitly deferred. If you run AWS data pipelines and you want the audit-trail story, the cost-tracking story, the contract-testing story — the shape is here. The `culvert-aws-*` slot in the layout is yours to fill. Write the S3 `BlobStore` first; run the contract tests; open a pull request. The framework is designed to take it. (`docs/framework-evolution/13-python-parity-release.md:27–31`)

**Beyond 0.1.0.** After the coordinated release the work that matters most is automated end-to-end tests in CI — the single highest-leverage change, because once you know the full round-trip works before every release, everything downstream becomes cheaper to validate. After that: the admin surface (quarantine review at minimum), streaming reference deployments, a proper operational handbook ("if you see error code X, do Y" — distinct from architectural docs), and whatever the community finds it needs to build the next adapter. The shape of the framework after 0.1.0 will be determined as much by what people build against it as by what I ship next.

## Closing thoughts

The boring truth about writing a framework is that the hard problem is not "how do I move bytes from A to B". The hard problem is "how do I make the movement of bytes legible, auditable, recoverable, and cheap to operate for years". Culvert is a serious attempt at the boring truth. The contracts are honest; the GCP implementation is real; the packaging plumbing will follow. It will not be the last attempt; better ones will come, and I would be delighted to read them. But it is, in 2026, a credible answer to the question "how do I run a cloud data pipeline I can stake my career on" — and one that, when the coordinated 0.1.0 ships, you will be able to pull from a registry rather than a git clone.

Until then: build from source. Write against the contracts. Run the tests. You will not be waiting long.

— *Joseph Aruja*

\begin{takeaways}
\textbf{Key takeaways}
\begin{itemize}
  \item Getting started today means building from source — \texttt{mvn install} for Java, \texttt{pip install -e} for Python — because nothing is on Maven Central or PyPI yet. The coordinated 0.1.0 publish is the next milestone; it is gated on both languages being ready, then a single Joseph-triggered release.
  \item Write to the contract, never to the adapter. \texttt{AutoConfig.discover()} hands you the right implementation at runtime via \texttt{ServiceLoader} (Java) or entry-points (Python); your business logic never imports a concrete adapter class directly.
  \item The roadmap in priority order: Wave D (packaging — the \texttt{culvert} PyPI distribution; Wave C adapter parity is done), coordinated 0.1.0 publish, then automated end-to-end CI. AWS and Azure are skeletons that prove the seam is real; production implementations are open invitations, not commitments.
  \item The framework's highest-leverage property is that the contract tests enforce conformance automatically. Every new adapter you write binds to the same test suite; the framework tells you whether you are conformant before you ship.
  \item The boring truth of data engineering is not moving bytes from A to B — it is making that movement legible, auditable, recoverable, and cheap to operate for years. That is what Culvert is a serious attempt at.
\end{itemize}
\end{takeaways}

\newpage
