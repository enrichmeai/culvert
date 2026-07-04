# Chapter 1 — Why Culvert

## The problem that won't go away

Mainframes were supposed to die thirty years ago. They didn't. Right now, every time you tap your bank card, there's a decent chance the transaction ends up on a COBOL programme running on a box older than most of the engineers who support it.

These machines aren't going anywhere. They work. They're paid for. They run rules the business forgot it wrote. They just happen to be terrible at analytics — which is where you come in, because someone decided the data needs to be in BigQuery by Monday.

On paper, "move data from the mainframe to BigQuery" sounds easy. In practice, it's a nightmare. The mainframe sends you fixed-width files with headers and trailers. Sometimes the files are chunked into five parts because the mainframe's network can't cope with anything bigger. Sometimes they're EBCDIC-encoded. Sometimes the schema quietly changes and the person who'd have warned you is on holiday.

A pipeline that handles all of that gracefully is a thing of beauty. A pipeline that handles it badly still runs — because the business needs the data — and you personally spend the next three years on-call for it. I've been that engineer. I don't want you to be that engineer.

## The scaffolding problem

Here is what happens every time a new team decides to build data pipelines seriously. They spend the first two weeks arguing about storage layout. Then two more weeks arguing about whether to use Airflow or something newer. Then someone writes an audit-trail utility that is nearly, but not quite, the same as the one the team next door wrote six months ago. Then someone else writes a quality-scoring function that is nearly, but not quite, the same as the one three other teams have written. Then the project goes live, it works, and they are all on-call for the scaffolding they built instead of the pipeline it was meant to carry.

I have watched this play out at scale. I have been the one writing the fourth slightly-different audit utility. The cost is not just engineering time — it is the operational burden that compounds when each team's slightly-different version breaks in a slightly-different way at three o'clock on a Sunday morning.

The underlying cause is not laziness. The underlying cause is that the scaffolding is not the product. Nobody budgets sprint time to publish a shared audit trail library. They budget sprint time to move the data. The scaffolding gets built in the cracks, privately, once per team, and never gets the maintenance it needs.

**Culvert is that scaffolding, built once properly.** Audit trails, cost tracking, structured logging, error classification, quality scoring, safe deletion, governance policies, schema types, GCP adapters — all of that is here, tested, versioned, and maintained. You build the pipeline. You don't rebuild the rails.

## What I actually built

The first iteration was GCP-only, by design and by name. By the time I retired it, I had:

- A **foundation library** that does not depend on Beam or Airflow — audit trails, cost tracking, quality scoring, lineage, error classification, schema types. Drop it into a Dataflow job, a Cloud Function, an Airflow DAG, or a random script on your laptop.
- An **ingestion layer** with Apache Beam transforms for HDR/TRL parsing, split-file reassembly, schema-driven validation, and error quarantine.
- An **orchestration layer** with Airflow operators, sensors, a DAG factory, and a dependency helper.
- A **transformation layer** with dbt macros for audit columns and PII masking.
- A **test library** with base classes, fake clients, and fixtures.
- GCP adapters for BigQuery, GCS, Pub/Sub, Secrets Manager, and Observability.
- Reference deployments that work out of the box.
- Terraform module sets, CI/CD suites.

And then I sat down and did a proper audit of the whole thing, and I asked one question: *how much of this is actually GCP code?*

## The audit that changed the name

I expected the answer to be "almost all of it." The framework lived in a directory called `gcp-pipeline-libraries`. Every module started with `gcp_pipeline_`. Every docstring opened with "GCP Pipeline Framework —..." When I went through the files one at a time and counted imports, the answer was about fifty-five percent. The other forty-five percent was already cloud-neutral, in fact if not in name.

The data-quality dimensions, the error taxonomy, the audit records, the lineage tracker, the structured logger, the run-ID generator, the alert manager, the OTEL bridge, the schema dataclasses, the HDR/TRL parser, the validators — none of these imported `google.cloud` anything. They lived in a directory called `gcp_pipeline_core` and they were not GCP code. They were generic Python with a GCP prefix glued to the front.

That is in-name-only coupling, and once you notice it you cannot un-notice it.

The smallest move that lets the framework grow into the shape it already half-was: name it honestly, extract language-neutral contracts, put cloud specifics behind adapters. Not a rewrite. Closer to admitting what already exists.

## The culvert metaphor

The framework has a name now: **Culvert**\index{Culvert}. A culvert is the engineered pipe that carries water from one side of a road to the other — controlled flow through a designed channel, holding back what should be held back, releasing what should be released, at a known rate.

The metaphor is exact. A data pipeline is a culvert: an engineered channel carrying records from a source to a destination, with controlled gates — governance, masking, quality checks — along the way. The name is short, distinctive, and unclaimed on PyPI and Maven Central, which are the three properties that matter for an open-source framework name.

## The thesis: start with GCP, discover cloud-neutrality, extract contracts

This book is not a GCP handbook with a framework bolted on at the end. It is the inverse.

The thesis is this: **if you start with one real cloud and build something that actually works in production, you discover that most of what you built was already cloud-neutral.** The GCP specifics turn out to be a relatively thin layer over contracts that could be satisfied by any cloud, any warehouse, any blob store. Once you see that, you can extract those contracts, put the GCP code behind adapters, and arrive — without any rewriting — at a framework that is cloud-neutral by design and polyglot by division of labour.

That is the journey this book documents. Not a theoretical exercise. Not a framework designed in a whiteboard session. A framework that grew out of a real GCP implementation and was honest enough about what it found to extract the shape that was already there.

## The Spring precedent

The cultural reference point I keep returning to is Spring Framework\index{Spring Framework}. The relevant fact about Spring is not that it ended up multi-database, multi-runtime, and multi-cloud. The relevant fact is the order in which it got there.

`spring-data-jpa` shipped first. It was the only persistence module for years. When `spring-data-mongodb` finally appeared, the JPA users did not have to learn a single new concept — the contracts Spring had defined were honest enough that MongoDB could plug into them. That works because `spring-core` was never contaminated with relational assumptions. It hosted *any* persistence model, even when only one existed.

That is the move here. I make the abstractions cloud-neutral. I ship the GCP implementation, which is the only one I have any business shipping because it is the only cloud I have run this framework against (`README.md:3`). If someone three years from now wants `culvert-aws-redshift` enough to write it, the contracts make that a 2–4 week build per service rather than a rewrite. If nobody ever writes it, the framework is no worse for the rename — the GCP code is the same code, with honest names.

## The contracts

The heart of Culvert is 16 language-neutral contracts: `Source`, `Sink`, `Transform`, `Pipeline`, `RuntimeContext`, `BlobStore`, `Warehouse`, `FinOpsSink`, `GovernancePolicy`, and their siblings (`README.md:5`). These are defined in `docs/CONTRACT.md` — a language-neutral specification, versioned at `1.0.0` (`docs/CONTRACT.md:3`). Any team can implement it in any language and produce records indistinguishable from those the framework produces (`docs/CONTRACT.md:9`).

The same 16 contracts are realised in two languages: Java interfaces in `data-pipeline-core-java`, Python Protocols in `data-pipeline-core`. They do not do the same job — that is the polyglot division of labour:

- **Contracts** — both languages implement the same spec
- **Dataflow / execution** — Java (Apache Beam), because that is what the GCP Beam runtime is optimised for
- **Orchestration** — complementary: Python owns the Airflow runtime side; Java owns the cloud-neutral DAG model
- **dbt / transform** — reused, because dbt is SQL and macros, not Java or Python

(`README.md:22–28`, `docs/framework-evolution/13-python-parity-release.md:20–27`)

## Where Culvert stands right now

I want to be direct about status, because books about software often describe the thing as it might be rather than as it is.

Culvert is **built and held**. The Java reactor has reached its `0.1.0` feature bar — all 16 contract interfaces have real GCP adapters, frozen at tag `java-0.1.0` (`README.md:79`). The Python side has completed contract reconciliation, core depth (including `DefaultRuntimeContext`, `dataquality`, concrete governance policies, the FinOps cost model), and GCP adapter parity for secrets and observability (`docs/framework-evolution/13-python-parity-release.md:57–82`).

What remains is packaging and the coordinated release: renaming the Python distributions from `data-pipeline-*` to `culvert-*`, setting up the PyPI publish workflow, and pulling the joint trigger — Maven Central for `com.enrichmeai.culvert:*` and PyPI for `culvert` — at the same moment (`docs/framework-evolution/13-python-parity-release.md:9–12`).

**Nothing is on Maven Central or PyPI yet.** The release gate is both languages ready; neither publishes alone. The GCP-only first iteration is simply retired — Culvert is the framework, and there is only one public story.

This is not a product pitch for something that might ship. It is a practitioner's account of something that is built, honest about where the last seam is.

## How this book is laid out

The structure follows the journey, not the architecture diagram.

**Part I — The case** (this chapter, plus Chapters 2 and 3) establishes why the problem exists, what the landscape of GCP data tools looks like, and gives you the zero-to-hero ramp on the concrete first cloud.

**Part II — The contract** (Chapters 4–6) is the heart of the book: cloud-neutral audit plus the Spring precedent as the GCP-origin story; the 16 contracts and `StageMetrics` in detail; the polyglot division of labour. Read this part if you read nothing else.

**Part III — The first implementation** (Chapters 7–11) goes through the GCP adapters layer by layer: storage and messaging, BigQuery and job control, Beam on Dataflow, dbt transformations, orchestration. This is the concrete cloud work.

**Part IV — Production concerns** (Chapters 12–17) covers observability, FinOps, governance, auto-config, contract testing, and CI/CD. The unglamorous stuff that turns a demo into something your CFO will fund.

**Part V — Beyond GCP** (Chapters 18–21) is about the cloud-neutral seam in practice: the AWS S3 and Azure Blob adapter skeletons that prove the design is real; an honest code review of the framework as it stands; working with AI coding agents as a genuine SDLC tool (not a hypothetical); and the getting-started guide.

By the end you will have a mental model for building production pipelines against cloud-neutral contracts — plus enough of a critical eye to tell when a framework (including this one) is not the right answer.

## A few ground rules

Before we go any further:

- I'll say **"you"** when I mean you, and **"we"** when I mean the team you and I would be on together.
- **The code samples are real.** Where I've simplified something for clarity, I'll say so. Everything in this book ships in the repo.
- **British spellings** (colour, behaviour, organisation). Sorry, not sorry.
- **I care about cost.** A lot. The single biggest mistake I see is teams building a pipeline that works and then realising it costs twelve thousand dollars a month to run. I'll flag costs whenever they show up.
- **Honest status.** If something is not yet shipped, I'll say so. The framework is built. The coordinated release is the last seam. I'd rather you know that now than discover it when you go to `pip install culvert` and find nothing there yet.

Right. Let's go.

\begin{takeaways}
\textbf{Key takeaways}
\begin{itemize}
  \item The hard problem of mainframe-to-cloud is not moving bytes — it is making the movement auditable, recoverable, and cheap enough to operate for years without rebuilding the same scaffolding every time.
  \item Every team that has ever done this has written the same scaffolding from scratch. Culvert is that scaffolding, built once properly and kept in one place.
  \item The Culvert thesis: start with one real cloud (GCP), discover most of the code is already cloud-neutral, extract language-neutral contracts, put cloud specifics behind adapters. No rewrite needed — just honesty about what was already there.
  \item Culvert is \textbf{built and held at 0.1.0} — Java reactor frozen at \texttt{java-0.1.0}, Python parity complete through Wave C. The release gate is Java \emph{and} Python both ready for a single coordinated publish to Maven Central and PyPI. Nothing is on either registry yet.
  \item Cost is a first-class concern throughout this book. If a choice saves engineering time but doubles the monthly bill, that is not a win.
\end{itemize}
\end{takeaways}

\newpage
