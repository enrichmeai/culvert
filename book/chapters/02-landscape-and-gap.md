# Chapter 2 — The Landscape and the Gap

## Google Cloud has the services. It does not have the answers.

If you walked into a room full of Google Cloud product managers in 2026 and asked "do you have everything I need to build a data pipeline?", they would, with complete sincerity, say yes. They would point at Cloud Storage for landing files. They would point at Pub/Sub for events. They would point at Dataflow for distributed processing. They would point at BigQuery for the warehouse, Cloud Composer for orchestration, Dataform and dbt-on-BigQuery for transformations, Datastream for change data capture, Data Fusion for low-code ETL, Dataplex for governance, and a half-dozen more.

They are not lying. The services exist. They are first-rate, they autoscale, they integrate, and they bill you per second.

What they will not tell you — because it is not their job to tell you — is that none of those services *together* form an opinionated framework. They are Lego bricks. There is no instruction sheet for "build a regulator-friendly mainframe-to-BigQuery pipeline that survives the next on-call rotation". You get to design the join between Pub/Sub and Dataflow yourself. You get to invent your own audit-trail format. You get to write the retry logic, the schema validator, the cost tracker, the data-quality scorer, the deletion workflow, the lineage propagation, the reconciliation report, the alert dispatcher, and the seventeen lines of bash that turn a Python source tree into a Dataflow Flex Template.

You will, in short, write a framework. Every team I have worked with has written some version of this framework. They have all written different versions of it. None of those versions has been good.

## What the open ecosystem actually offers

It is worth taking stock of the open-source landscape, because the picture is not flattering.

There are **runtime libraries** — Apache Beam, Apache Airflow, dbt, Datastream — and they are excellent at the thing they do, in isolation. There are **vendor SDKs** — `google-cloud-bigquery`, `google-cloud-storage` — and they are competent client libraries. There are **wrapper toolkits** that bundle a few of the above with conventions: Mage, Prefect, Dagster, Kedro, ZenML. Most of these are general-purpose orchestrators with the data-engineering ecosystem in mind, not opinionated GCP frameworks.

There are **enterprise reference architectures** from Google itself — beautifully diagrammed, freely downloadable, almost completely untestable. They give you a picture, not a codebase. The picture is not enough.

There are **internal frameworks** at every large GCP-using company on the planet. None of them are open. They are written for one organisation, by people who have moved on, in idioms nobody outside that organisation recognises.

There are, in short, no production-grade, open, GCP-specific, mainframe-aware, opinionated data-pipeline frameworks worth adopting. There are gaps everywhere.

## The eight gaps

If you make a list of the things every serious GCP pipeline team rebuilds from scratch, it looks something like this:

- **A mainframe-aware ingestion library.** Apache Beam does not understand HDR/TRL. Nobody's open library does either.
- **A schema-driven validator.** You either invent one or you write `if pd.isna(x):` ten thousand times.
- **A cost-tracking layer.** GCP billing tells you what last month cost. It does not tell you which entity, which run, which BigQuery query. You build that yourself or you fly blind.
- **A run-correlated audit trail.** Logs, metrics, audit events, dbt invocations, Dataflow jobs, Pub/Sub messages — they all have their own identifiers. Correlating them takes a deliberate identity (`run_id`) threaded through everything. No off-the-shelf library does this.
- **An error-classification taxonomy.** Validation, integration, and resource errors require different handling. Generic retry libraries treat them the same.
- **A data-deletion workflow.** "DELETE FROM" is illegal in most regulated industries. You need a workflow with approvers, holds, tombstones, and recoverable archives. Nobody ships this.
- **A reconciliation engine.** Did the envelope count match the ingested count match the BigQuery row count? Until you know, you are guessing.
- **A coordination layer for JOIN preconditions.** "Run the transform when both sources are loaded" sounds simple. In practice every team writes a slightly broken version.

This is the gap. It is not a missing service from Google; it is a missing *opinion* about how the existing services should be assembled.

## Why nobody has filled the gap

A reasonable question: if the gap is so obvious, why has the open ecosystem not closed it?

Three reasons, in my experience.

First, **the gap is mainframe-shaped**, and mainframe migrations are not glamorous. Open-source contributors prefer streaming Kafka pipelines into Snowflake to fixed-width files with EBCDIC encoding from Z/OS. The need is enormous; the contributor base is thin.

Second, **enterprise frameworks are written under NDA**. The teams who do solve this problem solve it on company time, with company data, behind company firewalls. Their code does not get extracted, generalised, and published.

Third, **the right framework is opinionated**, and opinions are unfashionable in the cloud-native world. The dominant style is "minimal toolkit, infinite extensibility". A framework that says "thou shalt use HDR/TRL, thou shalt have a `run_id`, thou shalt route bad records to a quarantine bucket" feels prescriptive in a way modern open source tries to avoid. But pipelines need that prescription. Without it, you do not have a pipeline; you have a kit of parts.

## A fourth reason: the cloud trap

There is a fourth reason, which the first three obscure, and it is the reason Culvert exists as it does rather than as yet another GCP-specific toolkit.

The teams that *do* build internal frameworks build them against one cloud. Naturally — the project is on GCP, the engineers know GCP, the company has GCP credits. The framework embeds GCP assumptions at every layer: it calls `google.cloud.bigquery` directly from the schema-validation code; the cost tracker references Dataflow slot prices as module-level constants; the audit-trail publisher is hard-wired to Pub/Sub. The framework solves the eight gaps above. But it has now created a ninth gap: **portability**. When the company acquires a division that runs on AWS, or when GCP's BigQuery pricing becomes inconvenient, or when a client demands an Azure deployment, the framework cannot move. You rewrite it or you abandon it.

I know this because I built that framework on GCP myself — Culvert's own first iteration — and the rewrite question arrived faster than I expected. The cloud-specific assumptions were not deliberate design choices; they were habits. Nobody on the team had thought carefully about which parts of the framework were about *data pipelines* and which parts were about *GCP*. It turned out most of the code was about data pipelines. The GCP parts were a thin layer on the outside. But thin layers that are not identified as thin layers become load-bearing walls.

The redesign document we wrote when this became clear (`docs/framework-evolution/02-redesign.md:1`) captures the commitment we made:

> *There is a small cloud-neutral core that contains the framework's domain primitives expressed as Python protocols and pure-Python implementations; there are cloud-specific modules that implement those protocols against a particular cloud's services; and the user composes a working pipeline by depending on the core plus whichever cloud modules they need. GCP is the first reference implementation because it already exists. AWS and Azure are reserved slots in the layout that the team is not committing to build but is committing not to design around.*

That commitment is what turned a GCP framework into Culvert. The gap is not just the eight things above; it is the eight things, plus the architectural discipline not to embed the cloud so deep into the answer that you cannot move.

## The language trap compounds it

There is a parallel trap on the language side, and I will not pretend I did not fall into it too.

The original framework was Python because I am comfortable in Python and because data engineering in the cloud defaults to Python. When we added the Java side — driven partly by the Beam execution layer, partly by the Spring-ecosystem engineers on the team — it would have been easy to treat Java as a second-class citizen: a thin client that calls the Python layer, or a set of Beam transforms that do not participate in the framework's contract surface.

We did not do that, and the reason is in `docs/framework-evolution/13-python-parity-release.md:22`:

> *One framework, two languages, not doing the same job. The contracts are the shared seam; each runtime owns the layers it's best at.*

That table is the whole polyglot story in two sentences. Java owns the Beam execution layer (Dataflow) and the cloud-neutral DAG model. Python owns the orchestration runtime (Airflow operators, sensors, DAG factories) and the transform layer (dbt is SQL, not Python, but the packaging is Python). Both sides implement the same contracts — the language-neutral specification in `docs/CONTRACT.md`. Neither side duplicates the other.

The alternative — a Python-only framework, or a framework where Java duplicates Python — fails in opposite directions. Python-only means the Beam execution layer either reimplements its own framework or calls back into Python from Java via a bridge nobody wants to maintain. Java-only means you have lost the Python data-engineering ecosystem entirely. The two-language split, with contracts as the seam, is the right answer. It is also the harder answer, which is why most frameworks do not attempt it.

## The contract as the portability boundary

The word "contract" does a lot of work in the Culvert story and I want to be precise about it here, because Chapter 4 goes deep on the mechanics.

A Culvert contract is a language-neutral specification of what a component must do. `docs/CONTRACT.md` defines the exact shape of every record the framework emits — the BigQuery table schemas for audit events, FinOps usage, and reconciliation records; the `run_id` format; the Pub/Sub trace propagation attributes; the three-bucket error classification (`docs/CONTRACT.md:248`). Any language that implements to this spec produces records indistinguishable from those produced by any other language. Python's `AuditEventPublisher` protocol and Java's `AuditEventPublisher` interface sit above the same wire format; the BigQuery table does not know or care which language wrote the row.

The contracts in code are Python `typing.Protocol` definitions and Java interfaces — two expressions of the same conceptual seam (`docs/framework-evolution/02-redesign.md:333`). When the Java side defined `BlobStore` as an interface and the Python side defined it as a `Protocol`, they had to agree on method names and semantics (`get`, `open`, `put`, `list`, `exists`, `delete`, `copy`) without either imposing its type system on the other. The agreement is `CONTRACT.md`. The implementations — `GCSBlobStore` in both languages, `S3BlobStore` in Java (skeleton), `ADLSBlobStore` in Java (skeleton) — are the adapters.

This is the answer to the portability gap. Not "write portable code" (an instruction nobody follows) but "write to contracts, implement adapters per cloud" (a structure that enforces portability without requiring heroism from the user).

## What Culvert is, and what it is not

Let me be honest about the current state, because dishonest enthusiasm is how frameworks develop bad reputations.

Culvert is **built**. The contracts exist. The GCP adapters exist — `GCSBlobStore`, `BigQueryWarehouse`, `BigQueryJobControlRepository`, `PubSubAuditPublisher`, and the rest — in both Python and Java, implementing the same contracts, passing the same contract test suite. The Java reactor is at `0.1.0` (tag `java-0.1.0`). Python Waves A through C are merged. The framework fills the eight gaps above for GCP pipelines today.

Culvert is **not published**. The coordinated release — Java to Maven Central as `com.enrichmeai.culvert:*` and Python to PyPI as `culvert` — is Wave D, gated on both languages being fully ready and on a Joseph-triggered publish (`docs/framework-evolution/13-python-parity-release.md:36`). Nothing auto-publishes; a version number on Maven Central or PyPI is irreversible, and we are not in a hurry to own that.

Culvert has **AWS and Azure skeletons, not implementations**. `data-pipeline-aws-s3-java` and `data-pipeline-azure-blob-java` exist as reserved slots that prove the design is cloud-neutral: an `S3BlobStore` implements the `BlobStore` contract and compiles cleanly. Neither has been tested against a real S3 bucket. The Python cloud-neutral skeletons are out of scope for the `0.1.0` release (`docs/framework-evolution/13-python-parity-release.md:30`). The AWS and Azure slots tell you what the framework *can* do, not what it currently does.

The GCP-only iteration Culvert grew from is retired. Culvert is the framework; the earlier code's only public legacy is the lessons in this book.

## The framework as the answer

Culvert is an answer. Not the answer; an answer. It tries to fill the eight gaps with concrete, opinionated, testable code, and it does so with the conventions of the rest of the ecosystem (Beam, Airflow, dbt, Terraform) rather than against them.

If you have worked in the JVM world, the closest cultural reference point is **Spring Framework**\index{Spring Framework}. Spring did not invent dependency injection; it took a set of patterns already loose in the community and gave them a name, an opinionated default, a thin core that the rest of the platform clipped onto, and a culture of *convention over configuration*. That combination — small core, plug-in modules, sensible defaults, an escape hatch when you need it — turned a kit of parts into an industry. Culvert is built on the same DNA. `data-pipeline-core` is the framework-agnostic kernel; the BigQuery, GCS, Pub/Sub, Dataflow, and Composer adapters clip on around it; the conventions (`EntitySchema`, `run_id`, error taxonomy) are the equivalent of Spring's component scan and stereotype annotations. The `RuntimeContext` is the framework's `ApplicationContext`. The `@pipeline`, `@source`, `@transform`, `@sink` decorators are the Python equivalent of `@SpringBootApplication`, `@Service`, `@Repository`. The auto-config registry (`docs/framework-evolution/02-redesign.md:641`) is Spring Boot's auto-configuration: add the GCP BigQuery adapter and it registers itself; the user does not write boilerplate.

It is opinionated where opinions matter:

- HDR/TRL is the assumed envelope. You can opt out, but the default is mainframe-shaped.
- `EntitySchema` is the source of truth. Validation, table creation, masking, fixtures — all read from it.
- `run_id` propagates everywhere. There is no log line, metric, audit event, dbt invocation, or cost record without one (`docs/CONTRACT.md:215`).
- Errors are classified. Validation does not retry. Integration does. Resource fails loudly (`docs/CONTRACT.md:248`).
- Cost is a metric. It lives next to throughput and latency, not in a separate billing dashboard.
- Deletion is a workflow. Nothing leaves the platform without an approval chain.
- Reconciliation is mandatory. A run is not green until envelope, valid, invalid, and BQ all agree — status `GREEN`, `YELLOW`, or `RED` (`docs/CONTRACT.md:191`).
- JOIN preconditions are explicit. The orchestrator waits, deterministically, for the right conditions.

It is also intentionally unopinionated where flexibility matters: you can run on Composer or substitute Cloud Functions; you can use BigQuery on-demand or flat-rate; you can emit to Cloud Trace or to any OTEL-compatible backend; you can publish to Maven Central and PyPI or to your internal Nexus.

It is cloud-neutral at the contract layer and GCP-first at the adapter layer. The contracts do not move when the cloud moves; the adapters do.

## What you get from this book

If you are reading this book, you are most likely in one of three situations.

You are **about to build a pipeline** like this and want to avoid the rake-step the rest of us all took. The next chapter covers the GCP fundamentals every pipeline depends on, with no prior assumption. Part II then gives you the contracts before the implementations, so you understand the design before you see the code.

You have **built a pipeline** like this — probably against GCP, probably in Python, probably with a framework that is now load-bearing and unmoveable — and you want to compare notes. The middle chapters of this book are for you. Pay particular attention to Chapter 4 (the portability boundary) and Chapter 18 (the cross-cloud adapter seam), which together tell you how to extract your own GCP-specific assumptions into adapters without rewriting what is already working.

You are **evaluating whether to adopt Culvert** rather than build your own. The honest code review in Chapter 19 and the cost model in Appendix C are for you. I have tried to be accurate about what is built, what is skeleton, and what is not yet started. The framework does not do everything; no framework does. But it fills the eight gaps above, and it fills them in a shape that does not lock you to a single cloud or a single language.

Whichever you are, the next chapter takes the GCP data services from zero. If you are already familiar, skim it; if you are not, it will save you weeks.

\begin{takeaways}
\textbf{Key takeaways}
\begin{itemize}
  \item GCP has all the bricks — Cloud Storage, Pub/Sub, Dataflow, BigQuery, Composer — but no instruction sheet for assembling them into a regulator-friendly pipeline. Every team writes that instruction sheet themselves, and every team writes a different one.
  \item The open-source ecosystem has runtime libraries and vendor SDKs, but nothing production-grade, GCP-specific, and mainframe-aware. The gap is structural, not temporary.
  \item The eight things every serious pipeline team rebuilds from scratch — mainframe-aware ingestion, schema validation, cost tracking, run-correlated audit, error taxonomy, deletion workflow, reconciliation, JOIN preconditions — are exactly what Culvert fills.
  \item A ninth gap compounds the eight: embedding GCP assumptions at every layer of an internal framework turns a thin adaptation layer into a load-bearing wall. The answer is contracts as the portability boundary and adapters as the cloud-specific layer.
  \item Culvert is one polyglot framework — Java and Python, not doing the same job but implementing the same contracts. Java owns Beam execution; Python owns orchestration and transform. The wire contract is language-neutral.
  \item Opinions are not a design smell. A framework that says nothing is a kit of parts. The right framework is prescriptive where it matters and flexible where it does not.
  \item Honest status: Culvert is built and held, GCP adapters are complete in both languages, AWS/Azure exist as design-proving skeletons. The coordinated 0.1.0 publish to Maven Central and PyPI is the remaining gate.
\end{itemize}
\end{takeaways}

\newpage
