---
title: "Building Cloud-Neutral Data Pipelines with Culvert"
subtitle: "A Developer's Field Guide to the Polyglot Culvert Framework"
author: "Joseph Aruja"
date: "2026"
lang: en-GB
toc: true
toc-depth: 2
numbersections: false
secnumdepth: 0
documentclass: book
classoption:
  - oneside
geometry: margin=1in
mainfont: "Georgia"
monofont: "Menlo"
fontsize: 11pt
linkcolor: NavyBlue
urlcolor: NavyBlue
toccolor: black
header-includes:
  - \usepackage{titlesec}
  - \usepackage{needspace}
  - \usepackage{fvextra}
  - \DefineVerbatimEnvironment{Highlighting}{Verbatim}{commandchars=\\\{\},breaklines,breakanywhere,fontsize=\small}
  - \widowpenalty=10000
  - \clubpenalty=10000
  - \displaywidowpenalty=10000
  - \raggedbottom
  - \pretolerance=2000
  - \tolerance=3000
  - \emergencystretch=1em
  - \titleformat{\chapter}[display]{\normalfont\huge\bfseries}{}{0pt}{\Huge}
  - \titleformat{\section}{\normalfont\Large\bfseries}{}{0pt}{}
  - \titleformat{\subsection}{\normalfont\large\bfseries}{}{0pt}{}
  - \titlespacing*{\section}{0pt}{2.5ex plus 1ex minus .2ex}{1.5ex plus .2ex}
  - \titlespacing*{\subsection}{0pt}{2.25ex plus 1ex minus .2ex}{1ex plus .2ex}
  - \usepackage{tikz}
  - \usepackage{graphicx}
  - \usepackage{float}
  - \usepackage{placeins}
  - \usepackage[font=small,labelfont=bf,skip=6pt]{caption}
  - \setlength{\intextsep}{14pt plus 2pt minus 2pt}
  - \setlength{\abovecaptionskip}{8pt}
  - \setlength{\belowcaptionskip}{6pt}
  - \usepackage{tocloft}
  - \renewcommand{\cftbeforechapskip}{0.4em}
  - \setlength{\cftbeforesecskip}{0.15em}
  - \renewcommand{\cftchapfont}{\normalfont\bfseries}
  - \renewcommand{\cftchappagefont}{\normalfont}
  - \usetikzlibrary{arrows.meta, positioning, shapes.geometric, calc, fit, backgrounds}
  - \usepackage{makeidx}
  - \makeindex
  - \renewcommand{\indexname}{Index}
  - \usepackage[framemethod=TikZ]{mdframed}
  - \newmdenv[backgroundcolor=gray!10, linecolor=gray!40, linewidth=0.6pt, leftmargin=0pt, rightmargin=0pt, innerleftmargin=14pt, innerrightmargin=14pt, innertopmargin=10pt, innerbottommargin=10pt, skipabove=12pt, skipbelow=12pt, roundcorner=4pt]{takeaways}
---

\newpage

\thispagestyle{empty}

\vspace*{2cm}

\begin{center}
\textit{Building Cloud-Neutral Data Pipelines with Culvert}

\textit{A Developer's Field Guide to the Polyglot Culvert Framework}
\end{center}

\vspace{1cm}

\noindent Copyright \copyright\ 2026 Good Shepherd Software Consultancy Limited.

\noindent Joseph Aruja asserts the moral right to be identified as the author of this work.

\vspace{0.5cm}

\noindent All rights reserved. No part of this publication may be reproduced, stored in a retrieval system, or transmitted in any form or by any means, electronic, mechanical, photocopying, recording or otherwise, without the prior written permission of the publisher, except in the case of brief quotations embodied in critical reviews and certain other non-commercial uses permitted by copyright law.

\vspace{0.5cm}

\noindent The information in this book is distributed on an "as is" basis, without warranty. While every precaution has been taken in the preparation of this work, neither the author nor the publisher shall have any liability to any person or entity with respect to any loss or damage caused or alleged to be caused directly or indirectly by the information contained herein.

\vspace{0.5cm}

\noindent The framework described in this book, Culvert (\texttt{com.enrichmeai.culvert} on Maven Central; \texttt{culvert} on PyPI), is developed at \texttt{github.com/enrichmeai/culvert} and licensed under its own open-source (MIT) terms, separate from this book. At the time of writing it is built and held at 0.1.0, pending its first coordinated release.

\vspace{1cm}

\noindent Published by Good Shepherd Press, an imprint of Good Shepherd Software Consultancy Limited, United Kingdom.

\noindent First edition: 2026.

\noindent ISBN: \texttt{<ISBN>}

\noindent VAT registration: GB \texttt{<VAT>}

\vspace{0.5cm}

\noindent Cover and interior diagrams: Joseph Aruja, using TikZ\index{TikZ} on \LaTeX.

\noindent Typeset with Pandoc\index{Pandoc} and Xe\LaTeX.

\noindent Body type: DejaVu Serif. Headings and diagrams: DejaVu Sans. Code: DejaVu Sans Mono.

\vspace{1cm}

\noindent For corrections, errata, or licensing enquiries: \texttt{joseph.a.aruja@gmail.com}

\vspace*{\fill}

\newpage

# Preface

I wrote my first line of professional Java in February 2001 — a Java EE point-of-sale system on EJB 2.0 and JSP for a chain of retail discount stores. Eight years in, by 2009, I was at Wm Morrison Supermarkets, building Message-Driven Beans and BPEL processes on Oracle SOA Suite that pushed prices and promotions out of Oracle Retail Price Management, through the Oracle Retail Integration Bus, into a mainframe-backed merchandising system. We monitored it with custom HP OpenView alerts and ran reconciliation against Oracle AQ queues.

Nobody had a word for what we were doing yet. The phrase *data pipeline* hadn't escaped Silicon Valley. We called it *integration*, and it was the kind of work that ate weekends and produced incident reports written in passive voice.

I've been doing some version of that work ever since. Twenty-five years now. Different decade, different stack, same underlying job: get business-critical data out of the system that owns it, into somewhere it can be analysed — without losing rows, leaking PII, or blowing the budget.

The customers move around. **Banking** — HSBC, First Direct, M&S Bank, Allstate Insurance. **Government** — Home Office, GOV.UK, DWP, UKBA, and NHS Spine, where I was technical lead on Release 7A and built the SAML single-sign-on framework reused across every Spine module. **Retail** — Morrison's, twice (the Evolve mainframe-integration programme in 2009, then the Ocado Direct Delivery and Store Pick projects in 2016–2017). **Transport** — Smart Ticketing on Greater Manchester Metrolink with Worldline; ITSO smart cards and contactless EMV under PCI-DSS. **Automotive** — Jaguar Land Rover, also twice; the VCS event-framework migration to GCP, and now the Subscription Control Platform. **Travel** — migrating Booking.com's booking engine to AWS EKS; Thomas Cook's iTour Connect. **Betting** — Caesars Digital and William Hill (UK and US), terminal estates and back-office. **Most recently**, a financial-services client where I'm currently Senior Lead Engineer on a mainframe-to-cloud migration.

Along the way I contributed to the Java standards as a member of the JSR 255\index{JSR 255} (JMX) specification group — a long way of saying I've spent a lot of years thinking about what makes a *good interface* hold up under production load.

The platforms keep changing. Oracle SOA Suite. JBoss EAP. WebLogic. Spring. Dropwizard. AWS EKS. GCP. Kubernetes. The hard parts never do. Audit trails. Cost tracking. Error classification. Schema drift. Reconciliation. The stuff that makes a pipeline trustworthy rather than merely functional.

Around year fifteen I noticed something embarrassing: every team I joined was rebuilding the same scaffolding. Different language, different cloud, same scaffolding. By year twenty I was tired enough of writing it from scratch that I sat down and built a proper framework. I started with GCP — a single real cloud, a concrete target, no hand-waving. Then something interesting happened: when I looked hard at what I'd built, most of the code was already cloud-neutral. The contracts — the language-neutral interfaces that every adapter implements — were the seam. Extract those, and the GCP implementation becomes the *first* implementation rather than the only one. That extraction became **Culvert** — a cloud-agnostic data-pipeline framework, which is the idea this whole book exists to argue: the same pipeline, defined once against contracts, running today on GCP and AWS, with Azure on the roadmap. The repo this book is a tour of is `culvert`, built at 0.1.0 and held; the GCP-only first iteration is retired, its lessons now the origin arc of what you are reading.

The design language was deliberate. I had spent a decade on Spring projects and watched what Spring Framework had done for the JVM: a small framework-agnostic core, opinionated modules clipped on around it, conventions over configuration, escape hatches when you needed them. The result was an industry. Culvert borrows that DNA without apology. There is a Spring-shaped framework hiding underneath the dbt models and the Beam jobs, and I think it deserves to be called that.

This book is the long-form version of the conversation I've been having for the last decade with senior engineers, architects, and CFOs at banks and government departments. It's the answer to the question they always end up asking: *"How do we do this in a way we can defend to a regulator and afford to operate?"*

**Who I wrote this for.** Three kinds of reader:

- You're newish to GCP and you want to learn how pipelines actually work in the real world. Start at Chapter 1 and go in order. Chapters 2 and 3 give you the landscape and the basics before we touch any framework code.
- You're an experienced engineer and you just want the patterns. Skip to Chapters 4 through 12. That's where the meat is.
- You're an architect trying to decide whether to adopt this thing or build your own. Read Chapters 2, 19 (the honest code review) and Appendix C (the cost model). That'll tell you most of what you need.

**What this book isn't.** It's not a certification cram. It's not a GUI walkthrough. I assume you've clicked around the Google Cloud Console before and you know what BigQuery is, even if you've never written a Dataflow job.

**What you'll be able to do by the end.** Take an unfamiliar mainframe extract and design an ingestion pipeline for it in an afternoon. Add a new entity to a running Culvert deployment in less than a working day. Diagnose a failed run end-to-end using only an audit trail and a run ID. Justify, with real numbers, whether your team should be paying for Cloud Composer. Read a deployment workflow and tell what it actually does. Argue convincingly with your security team about IAM, KMS, and lifecycle policies.

**A note on opinions.** When I tell you that audit-trail propagation matters, or that Composer is overkill below a certain scale, that's not theory. That's two decades of post-incident reviews talking. The opinions in this book are *empirically* what survives in production, calibrated across eight industries and the regulatory regimes that go with them — FCA\index{FCA}, PCI-DSS\index{PCI-DSS}, GOV-grade, NHS data, ITSO\index{ITSO} transport, US gaming.

**A note on honesty.** Chapter 19 is a code review of my own framework. I've tried to make it useful rather than flattering. Culvert has real strengths and real weaknesses, and I'd rather you understood both before adopting it. If this book helps you build something better, that's a win I'll happily take.

Where I could use a story instead of a bullet list, I did. Where I could cut a paragraph, I cut it. If something's still clunky, tell me and I'll fix it in the next edition.

Right. Coffee in hand? Let's go.

Joseph Aruja, Leeds, 2026

\newpage

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

I know this because I built exactly that framework on GCP — Culvert's first, GCP-only iteration — and the rewrite question arrived faster than I expected. The cloud-specific assumptions were not deliberate design choices; they were habits. Nobody on the team had thought carefully about which parts of the framework were about *data pipelines* and which parts were about *GCP*. It turned out most of the code was about data pipelines. The GCP parts were a thin layer on the outside. But thin layers that are not identified as thin layers become load-bearing walls.

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

Culvert now runs on **two clouds**. GCP is the first full implementation; AWS is a real Java adapter family — S3 (`BlobStore`), Secrets Manager (`SecretProvider`), SQS (`Source`/`Sink`), DynamoDB (`JobControlRepository`, with the transactional conditional writes BigQuery's implementation cannot give you), Athena (`Warehouse`, including the external-table load path), and CloudWatch (observability) — proven locally against LocalStack, with the same ingestion pipeline running on both clouds via an adapter swap (Chapter [Cross-Cloud]). **Azure is explicitly later**: `data-pipeline-azure-blob-java` remains a single-method skeleton that proves the seam compiles, and I am not going to pretend otherwise. Python adapters beyond GCP are also later. Two clouds proven, one on the roadmap — that is the honest state.

The GCP-only iteration Culvert grew out of is retired. Culvert is the framework; there is one public story, and this book is it.

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

# Chapter 3 — GCP Fundamentals, Zero to Hero

This chapter is the on-ramp. If you have never built a data pipeline on Google Cloud, read it carefully. If you have, skim it for the conventions — and the vocabulary — the rest of this book assumes. Either way, read the final section, because the point of this chapter is not to teach you GCP. It is to show you *why Culvert's first full implementation lives there*, and to name every GCP service that sits behind an adapter before we start opening those adapters up in Part III.

## The concrete first cloud

Every framework has to start somewhere. Culvert started on GCP.

That was not an arbitrary call. The team had built three production pipeline deployments on Google Cloud before writing a line of framework code. We had opinions forged in the middle of the night when a Dataflow job drained off the end of a watermark and nobody's alert fired. We knew which knobs mattered and which were dials stuck at their factory settings. We knew that the 30-line "hello Beam" example in every Google tutorial conceals roughly eight weeks of production work — quarantine handling, reconciliation, audit trails, IAM segregation, cost tracking, dead-letter routing — and we were tired of rewriting that same eight weeks for each new pipeline.

The framework came out of that frustration. The GCP implementation is the *real* one: all 16 contract interfaces have living adapter classes; the Java reactor has been frozen at `java-0.1.0` with the full adapter set in place (`README.md`). When Part III walks you through the adapter modules — `data-pipeline-gcp-gcs-java`, `data-pipeline-gcp-pubsub-java`, `data-pipeline-gcp-bigquery-java`, `data-pipeline-gcp-dataflow-java`, `data-pipeline-gcp-secrets-java`, `data-pipeline-gcp-observability-java` — this chapter is the map you will want to have already read.

So: GCP fundamentals. One mental model. The core services in one paragraph each. A handful of minimal examples that demonstrate not what the framework does but what it *saves you from*. Then forward into the rest of the book.

## The mental model

A data pipeline on GCP, at the most reductive level, is a four-stage object:

```
[ Source ] → [ Land ] → [ Process ] → [ Serve ]
```

- **Source** is wherever the data is born — a mainframe extract, a Postgres database, a third-party SaaS export, a Kafka topic.
- **Land** is where it first arrives in the platform — almost always Cloud Storage.
- **Process** is the work of validating, transforming, joining, and shaping it — Dataflow, dbt, BigQuery scheduled queries.
- **Serve** is wherever consumers reach in — BigQuery for analysts, Looker for dashboards, Pub/Sub for downstream systems.

Every service we will discuss occupies one of those boxes. Once you have the boxes in mind, the services stop feeling like a confusing menu and start feeling like a small set of choices *per box*. Culvert's contracts map directly onto these stages: `Source` and `Sink` contracts govern data entry and exit; `Warehouse` governs the serve layer; `Pipeline` and `PipelineStage` govern the processing graph. The GCP adapters are the implementations that wire those contracts to the real services. The mapping is not accidental.

## The core services in one paragraph each

**Cloud Storage (GCS).**\index{Cloud Storage} Object storage. Buckets contain objects; objects have keys; everything is HTTP under the hood. Storage classes (Standard, Nearline, Coldline, Archive) trade cost against retrieval latency. Lifecycle rules\index{Cloud Storage!lifecycle rules} move objects between classes automatically. Notifications\index{Cloud Storage!notifications} let GCS publish to Pub/Sub when an object lands — that event is usually the starting gun for a Culvert pipeline run. The unit of work is the object, not the file system. The adapter is `GcsBlobStore`, which implements the `BlobStore` contract (`data-pipeline-gcp-gcs-java`, `GcsBlobStore.java:1–49`); chapters 7 and 8 cover it in full.

**Pub/Sub.**\index{Pub/Sub} Managed publish/subscribe messaging. Publishers push messages to a topic\index{Pub/Sub!topics}; subscribers pull — or get pushed — from a subscription\index{Pub/Sub!subscriptions}. At-least-once delivery by default; exactly-once is available with a configuration flip. Acknowledgements are required, retries are automatic, dead-letter\index{Pub/Sub!dead letter} routing is built in. Pub/Sub is the GCP equivalent of Kafka for most use cases — simpler, less tunable, and almost always good enough. The Culvert adapters are `PubSubSource` (implementing `Source`) and `PubSubSink` (implementing `Sink`) in `data-pipeline-gcp-pubsub-java`; chapter 7 covers both. Note the at-most-once trade-off baked into `PubSubSource.read()`: messages are acknowledged before the iterator is returned to the caller (`PubSubSource.java:24–27`). That is a deliberate contract-level decision — callers needing at-least-once must wire a separate subscriber.

**Dataflow.**\index{Dataflow} Managed runner for Apache Beam\index{Apache Beam} pipelines. You write a Beam program in Java; Dataflow takes it, autoscales\index{Dataflow!autoscaling} the worker pool, and runs it as either a batch or a streaming job. Beam's programming model is map/reduce/group with side inputs and side outputs; it parallelises naturally; it handles late-arriving data with watermarks. Culvert's adapter is `DataflowPipeline`, which implements the `Pipeline` contract and bridges it to Beam's `DataflowRunner` (`data-pipeline-gcp-dataflow-java`, `DataflowPipeline.java:29–56`). The contract is intentionally scheduler-agnostic — it describes the DAG, not how stages execute. Chapter 9 is dedicated to this adapter.

**BigQuery.**\index{BigQuery} A serverless analytics warehouse. You create datasets\index{BigQuery!datasets}; datasets contain tables; tables can be partitioned\index{BigQuery!partitioning} and clustered. Storage is columnar and compressed. Queries scan data and bill on bytes scanned (on-demand) or slot-seconds\index{BigQuery!slots} (flat rate). BigQuery is unique among warehouses in that there is no cluster to manage; you cannot oversize or undersize it. The Culvert adapter is `BigQueryWarehouse`, which implements the `Warehouse` contract and issues all operations as BigQuery jobs (`data-pipeline-gcp-bigquery-java`, `BigQueryWarehouse.java:35–48`). Chapter 8 covers the warehouse, job control, and the FinOps sink that writes cost metrics back into BigQuery itself.

**Cloud Composer.**\index{Cloud Composer} Managed Apache Airflow\index{Airflow} on GKE. You write DAGs in Python; Composer schedules, runs, monitors, and retries them. Cloud Composer 2 starts at roughly 300 USD per month before you schedule a single task.\index{Cloud Composer!cost} Use it when you genuinely need Airflow; use Cloud Functions or Cloud Run Jobs when you do not.\index{Cloud Composer!alternatives} Culvert's orchestration module (`data-pipeline-orchestration-java`) provides a cloud-neutral DAG model — `DagSpec` and `TaskSpec` — with a Composer renderer that emits Python DAG files. The Python side owns the Airflow runtime itself. Chapter 11 covers the full orchestration story.

**Secret Manager.**\index{Secret Manager} Managed secret storage — API keys, database passwords, service-account credentials. Secrets are versioned; access is logged; rotation is first-class. The Culvert adapter is `SecretManagerProvider`, which implements the `SecretProvider` contract and resolves secrets at `projects/{projectId}/secrets/{name}/versions/{version}` (`data-pipeline-gcp-secrets-java`, `SecretManagerProvider.java:1–40`). The no-arg constructor reads `GCP_PROJECT_ID` from the environment and registers via `ServiceLoader`, so `AutoConfig.discover()` finds it automatically. Secrets never touch logs — not at DEBUG, not ever.

**Cloud Trace and Cloud Monitoring.**\index{Cloud Trace}\index{Cloud Monitoring} Tracing and metrics. Cloud Trace stores distributed spans; Cloud Monitoring stores time-series metrics and drives alert policies. Culvert's adapter is `CloudTraceObservabilityHook`, which implements the `ObservabilityHook` contract and bridges to OpenTelemetry — whose `SdkTracerProvider` is wired to the GCP exporter by the caller (`data-pipeline-gcp-observability-java`, `CloudTraceObservabilityHook.java:19–40`). The design is deliberately decoupled: the hook does not know it is talking to GCP; the OTel exporter configuration does. `CloudMonitoringMetricsHook` provides the metrics side. Chapter 12 covers observability and lineage in full.

That is, modulo a few specialised services we will meet in passing (Cloud Data Catalog for lineage, Cloud KMS for customer-managed encryption, Workload Identity Federation for keyless CI authentication), the entire GCP substrate this book uses.

## The simplest possible GCP pipeline, in 30 lines

To make all of the above concrete, here is the smallest pipeline that does something useful: read a CSV from GCS, count the rows, write the count to BigQuery.

```python
import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions

class CountToRow(beam.DoFn):
    def process(self, element):
        yield {"file_uri": "gs://example/in.csv", "row_count": element}

def run():
    options = PipelineOptions(
        runner="DataflowRunner",
        project="my-project",
        region="europe-west2",
        temp_location="gs://example/tmp",
        staging_location="gs://example/staging",
    )

    with beam.Pipeline(options=options) as p:
        (
            p
            | "Read"      >> beam.io.ReadFromText("gs://example/in.csv", skip_header_lines=1)
            | "ToOnes"    >> beam.Map(lambda _: 1)
            | "Sum"       >> beam.CombineGlobally(sum)
            | "ToRow"     >> beam.ParDo(CountToRow())
            | "WriteBQ"   >> beam.io.WriteToBigQuery(
                "my-project:example.row_counts",
                schema="file_uri:STRING,row_count:INTEGER",
                write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND,
                create_disposition=beam.io.BigQueryDisposition.CREATE_IF_NEEDED,
            )
        )

if __name__ == "__main__":
    run()
```

That is a complete, runnable pipeline. It is also a useless one in production: there is no schema validation, no error handling, no audit trail, no cost tracking, no reconciliation, no `run_id`. None of those are optional extras. Every pipeline that handles real data, real volumes, and real downstream consumers needs all of them. The gap between this 30-line example and a production-ready Beam job is eight weeks of work the first time you close it. It is the work Culvert was built to carry for you.

## The simplest possible orchestration, in 20 lines

A trivially small Airflow DAG that runs the above:

```python
from airflow import DAG
from airflow.providers.google.cloud.operators.dataflow import DataflowCreatePythonJobOperator
from datetime import datetime

with DAG(
    dag_id="example_count",
    start_date=datetime(2026, 1, 1),
    schedule="@daily",
    catchup=False,
) as dag:
    DataflowCreatePythonJobOperator(
        task_id="count_rows",
        py_file="gs://example/code/count.py",
        job_name="example-count-{{ ds_nodash }}",
        location="europe-west2",
        options={"runner": "DataflowRunner"},
    )
```

Complete, runnable, and missing every important production property. No retry policy. No SLA. No alerting. No dependency on upstream landing. No audit. No idempotence. Culvert's orchestration module (`data-pipeline-orchestration-java`) provides all of those by composition — you define a `DagSpec` once, and the Composer renderer emits a Python DAG with them included.

## The simplest possible transformation, in 10 lines

A minimal dbt model:

```sql
-- models/example/row_counts_daily.sql
{{ config(materialized='table') }}

SELECT
    DATE(load_ts) AS load_date,
    SUM(row_count) AS total_rows
FROM {{ source('example', 'row_counts') }}
GROUP BY 1
```

Useful, simple, and missing audit columns, PII masking, incremental materialisation, and tests. dbt is the one component in Culvert that is genuinely language-neutral — SQL plus macros — and the framework does not wrap it: `data-pipeline-transform` packages the dbt project directly, with no Java or Python translation layer on top. Chapter 10 covers the reasoning.

## The hidden complexity of the simple version

If you ran the three snippets above in sequence, you would have a "pipeline" that:

- Has no encryption at rest or in transit beyond what GCP applies by default.
- Has no IAM segregation (every service runs as your user credentials).
- Has no dead-letter handling (a bad row silently drops the message).
- Has no observability beyond stdout and whatever Dataflow logs to Cloud Logging by default.
- Has no testing harness — you cannot run a unit test against any part of it.
- Has no concept of who triggered what when, or what the source row count was, or whether the BigQuery row count agrees with it.
- Costs roughly the same as the production version because it leaves Composer and Pub/Sub running whether they have work to do or not.

Every line of Culvert exists to close one of those gaps. The `GcsBlobStore` exists because object stores without lifecycle rules and uniform-bucket-level access quietly become compliance problems. The `SecretManagerProvider` exists because hardcoding credentials is not a shortcut — it is a debt that compounds. The `CloudTraceObservabilityHook` exists because "observe it in stdout" is not observability. As we walk through the adapter modules in Part III, recognise that what looks like complexity is, in almost every case, *load-bearing* complexity — there because the simple version was wrong in production.

The framework does not make pipelines simpler. It makes the right amount of complexity easier to carry.

## Culvert's GCP adapter map

Before we leave this chapter, here is a one-table reference that maps the six GCP adapter modules to the contracts they implement and the chapters that cover them in detail. You will want this when the later chapters refer back to module names.

| Module | Key classes | Contract(s) | Chapter |
|---|---|---|---|
| `data-pipeline-gcp-gcs-java` | `GcsBlobStore`, `QuarantineHandler`, `GcsCostTracker` | `BlobStore`, `FinOpsSink` | 7, 13 |
| `data-pipeline-gcp-pubsub-java` | `PubSubSource`, `PubSubSink`, `PubSubCostTracker` | `Source`, `Sink`, `FinOpsSink` | 7, 13 |
| `data-pipeline-gcp-bigquery-java` | `BigQueryWarehouse`, `BigQueryFinOpsSink`, `BigQueryAuditEventPublisher` | `Warehouse`, `FinOpsSink` | 8, 13 |
| `data-pipeline-gcp-dataflow-java` | `DataflowPipeline` | `Pipeline` | 9 |
| `data-pipeline-gcp-secrets-java` | `SecretManagerProvider` | `SecretProvider` | (cross-cutting) |
| `data-pipeline-gcp-observability-java` | `CloudTraceObservabilityHook`, `CloudMonitoringMetricsHook`, `DataCatalogLineageEmitter` | `ObservabilityHook` | 12 |

All six modules are in the Java reactor under `data-pipeline-libraries-java/` (`README.md:31–37`). Equivalent Python adapters live under `data-pipeline-libraries/data-pipeline-gcp-{gcs,pubsub,bigquery,secrets,observability}/` and implement the same contracts via Python Protocols.

## A glossary refresher

A few terms you will see throughout the book, defined once here:\index{ODP}\index{FDP}\index{CDP}\index{run\_id}\index{HDR/TRL}\index{quarantine}\index{reconciliation}

- **ODP** — Original Data Product. The untransformed BigQuery layer that mirrors source extracts.
- **FDP** — Foundation Data Product. The clean, business-shaped layer.
- **CDP** — Consumable Data Product. Narrow, contracted views derived from FDP.
- **Run ID** — A unique identifier per pipeline execution, threaded through every artefact: the GCS object key, the BigQuery audit row, the Pub/Sub message attribute, the Cloud Trace span.
- **HDR/TRL** — Header/Trailer envelope on a mainframe extract file. The envelope row-count claim is what reconciliation checks against.
- **Quarantine** — The four-stage workflow (REVIEW, HOLD, DELETE, ARCHIVE) for rejects and intentional deletions. `QuarantineHandler` in `data-pipeline-gcp-gcs-java` is the implementation.
- **Reconciliation** — The check that envelope count, valid count, invalid count, and BigQuery row count all agree. A pipeline that does not reconcile cannot be trusted.

## What zero to hero looks like

By the end of this book you will be able to:

- Take an unfamiliar data source and design a Culvert-backed ingestion pipeline for it in an afternoon.
- Add a new entity to a running framework deployment in less than a working day, by implementing the contracts and letting `AutoConfig.discover()` wire it in.
- Diagnose a failed run end-to-end using only the audit trail, the run ID, and Cloud Trace.
- Justify, with numbers, the choice between Composer and Cloud Functions for orchestration.
- Read a `DagSpec` and understand what the Composer renderer will produce from it.
- Know which six adapter modules to look in when something goes wrong on GCP.

That is hero. The GCP fundamentals in this chapter are the ground beneath it. The contracts in Part II are the frame. The adapters in Part III are what makes the frame load-bearing.

\begin{takeaways}
\textbf{Key takeaways}
\begin{itemize}
  \item Every GCP pipeline is a four-stage object: Source → Land → Process → Serve. Culvert's contract set maps directly onto those stages; the six GCP adapter modules are what make the mapping real.
  \item The 30-line Beam example is complete and runnable. It is also missing reconciliation, audit, cost tracking, PII masking, retries, dead-letter handling, and IAM segregation. Each of those gaps is load-bearing in production — and closing them is what Culvert was built to carry.
  \item The six GCP adapter modules — \texttt{data-pipeline-gcp-\{gcs,pubsub,bigquery,dataflow,secrets,observability\}-java} — are all present and frozen at \texttt{java-0.1.0}. Nothing is published yet; the release gate is Java and Python both ready, then a single coordinated \texttt{0.1.0} to Maven Central and PyPI.
  \item \texttt{ODP}, \texttt{FDP}, \texttt{CDP}, \texttt{run\_id}, \texttt{HDR/TRL}, \texttt{quarantine}, and \texttt{reconciliation} are framework vocabulary used throughout the book; they are defined once here.
\end{itemize}
\end{takeaways}

\newpage

# Chapter 4 — Contracts as the Portability Boundary

## Why I renamed a perfectly working framework

The framework has a name now: **Culvert**\index{Culvert}. A culvert is the engineered pipe that carries water from one side of a road to the other — controlled flow through a designed channel, holding back what should be held back, releasing what should be released, at a known rate. The metaphor is exact. A data pipeline is a culvert: an engineered channel carrying records from a source to a destination, with controlled gates — governance, masking, quality checks — along the way. The name is short, distinctive, and as of this writing unclaimed on PyPI under the `culvert` namespace, which is the property that matters most when you are planning a coordinated open-source release. The book you are reading was written about the *reference implementation* — the GCP-specific deployment at `github.com/enrichmeai/culvert`\index{Culvert!reference implementation} that the earlier chapters document. **Culvert is the framework that reference grew into.**

The Python distributions are currently named `data-pipeline-core`, `data-pipeline-gcp-bigquery`, `data-pipeline-gcp-gcs`, and `data-pipeline-gcp-pubsub`. They will, in the coordinated release, become `culvert-core`\index{culvert-core} and the matching `culvert-gcp-*` family. The namespace `culvert` on PyPI is reserved; the Java groupId `com.enrichmeai.culvert` is in use in the reactor pom at `0.1.0`\index{Culvert!java-0.1.0} right now. I want to explain what happened between "GCP pipeline framework" and "Culvert 0.1.0", because the path is the point.

## The audit

I want to explain the rename, because at first glance this looks like exactly the kind of cosmetic renaming that gets engineers fired in their second year. The first time someone proposed I rename a working framework I rolled my eyes hard enough to dislodge a contact lens. I had a working system. The packages were on PyPI. Pipelines were running in production against it. What sort of muppet rewrites the package names of a system that already works?

The honest answer is that I sat down and did a proper audit of the codebase against the question: *how much of this is actually GCP code?*\index{cloud-neutral contracts!audit}

I expected the answer to be "almost all of it." The framework lived in a directory called `gcp-pipeline-libraries`. Every Python module started with `gcp_pipeline_`. Every docstring opened with "GCP Pipeline Framework —". When I went through the files one at a time and counted imports, the answer was about fifty-five per cent. The other forty-five-or-so per cent was already cloud-neutral, in fact if not in name.

The data-quality dimensions, the error taxonomy, the audit records, the lineage tracker, the structured logger, the run-ID generator, the alert manager, the OTEL bridge, the schema dataclasses, the HDR/TRL parser, the validators — none of these imported `google.cloud` anything. They lived in a directory called `gcp_pipeline_core` and they were not GCP code. They were generic Python with a GCP prefix glued to the front.

That is in-name-only coupling, and once you notice it you cannot un-notice it. The rename is the smallest move that lets the framework grow into the shape it already half-is. It is not a rewrite. It is closer to admitting what already exists.

## The Spring precedent, told properly

The cultural reference point I keep returning to is Spring Framework\index{Spring Framework}. The relevant fact about Spring is *not* that it ended up multi-database, multi-runtime, and multi-cloud. The relevant fact is the order in which it got there.

`spring-data-jpa` shipped first. It was the only persistence module for years. It targeted relational databases through a perfectly good Java standard, and people built real applications against it without ever having to wonder whether Spring would one day support a document store. When `spring-data-mongodb` finally appeared, it was written largely by the MongoDB team itself, and the JPA users did not have to learn a single new concept; the contracts that `spring-data` had defined — repositories, queries, conversion services — were honest enough that MongoDB could plug into them without contorting itself or contorting the JPA users' code.

What makes that story work is that `spring-core` was never contaminated with relational assumptions. It hosted *any* persistence model, even when only one existed in the wild. The team made the abstractions cloud-neutral — to drag the metaphor forward by twenty years — and then shipped the implementation they actually needed. The other implementations either followed from a community that wanted them, or were built deliberately and much later. They were not promised; they were enabled.

That is the move Culvert makes. The abstractions are cloud-neutral. The GCP implementation is the only one worth shipping right now, because it is the only cloud this framework has been run against in anger. AWS and Azure skeleton adapters exist in the reactor (`data-pipeline-aws-s3-java/`, `data-pipeline-azure-blob-java/`), proving the seam compiles — they are not production-ready and they are not pretending to be. If someone three years from now wants `culvert-aws-redshift` enough to write it, the contracts make that a 2–4 week build per service rather than a rewrite. If nobody ever writes it, the framework is no worse for the rename — the GCP code is the same code, with honest names.\index{Culvert!AWS skeleton}\index{Culvert!Azure skeleton}

## What was already cloud-neutral

The audit's most useful finding was the inventory of code that contains zero references to `google`, `bigquery`, `gcs`, `dataflow`, or `pubsub`. The list is longer than I expected.

The entire data-quality subpackage — `checker.py`, `dimensions.py`, `scoring.py`, `anomaly.py`, `reporting.py`. These operate on `List[Dict[str, Any]]` and have always done so. The error taxonomy — every exception class, the classifier, the retry policy, the in-memory storage. The audit primitives — pure dataclasses and dict assembly. The whole of the data-deletion logic except for one GCS subclass — the malformation detector, the quarantine manager, the deletion workflow, the recovery bookkeeping. The HDR/TRL parser, modulo one `gs://`-sniffing block that disappears once you inject a `BlobStore`. The monitoring primitives: `MetricsCollector`, `HealthChecker`, `AlertManager`, the OTEL tracing and context modules. The structured logger. The run-ID generator. The schema dataclasses. The finops cost-metrics model and the label dataclass.

None of this code was wrong. The naming was wrong. These modules had been generic the whole time; calling them GCP because they lived under a `gcp_pipeline_*` namespace was a category error I committed when I first laid the repo out, and the audit caught me at it.

What the rename does for this code is honest labelling. `data-pipeline-core` — the module that will become `culvert-core` in the coordinated release — is allowed to import `typing_extensions`, `pydantic`, and `opentelemetry-api`. It is not allowed to import `google.cloud.anything`.

## What is genuinely GCP

The other half of the audit is the inventory of code that is GCP-coupled by design. I want to name these by name, because I am not going to pretend they are not what they are.

The BigQuery client wrapper. The GCS client wrapper. The Pub/Sub client wrapper. The BigQuery-backed job-control repository — every method builds parameterised BigQuery SQL and ships it through `bigquery.Client.query()`; the class has dozens of BigQuery references across hundreds of lines, and that is correct, because it is doing BigQuery work\index{job control repository}. The cost tracker with its `BQ_COST_PER_TIB` constant. The Pub/Sub audit publisher. The Cloud Monitoring alert backend. The GCS error storage and recovery manager. The GCS file lifecycle and archiver. The Dataplex governance hooks. The entire Beam-on-Dataflow execution package. The entire Composer DAG factory built around `airflow.providers.google.cloud.*`. The dbt macros that emit BigQuery SQL.

All of this stays GCP. All of it gets named honestly: `data-pipeline-gcp-bigquery`, `data-pipeline-gcp-dataflow`, `data-pipeline-gcp-composer`, `data-pipeline-gcp-gcs`, `data-pipeline-gcp-pubsub`, `data-pipeline-gcp-dataplex`, `data-pipeline-gcp-observability`, `data-pipeline-gcp-secrets`, `data-pipeline-gcp-dbt`. These are first-class modules in the framework, not afterthoughts. They are what makes the framework useful to a team running on GCP today.

The point is that they are no longer the *whole* framework. They are the GCP family within it.

## Sixteen contracts

The audit sharpened into a concrete question: what is the minimum set of abstractions that a cloud-neutral data pipeline framework needs to express? I landed on sixteen interfaces, mirrored across Java and Python, plus the `StageMetrics` value type.

The sixteen, in the Java package `com.enrichmeai.culvert.contracts` (`data-pipeline-libraries-java/data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/`\index{Culvert!contract directory}):

```text
Source             — anything that yields records (lazy iterator)
Sink               — anything that consumes records
Transform          — anything that maps records from one type to another
Pipeline           — a named, validated graph of stages
PipelineStage      — one node in that graph: name, inputs, outputs, execute()
RuntimeContext     — the framework's DI container (run_id, config, secrets, …)
JobControlRepository — the job ledger (create, update, mark failed, retry, …)
BlobStore          — object storage (get, put, list, exists, delete, copy)
Warehouse          — tabular query/load (query, execute, load_from_uri, merge)
AuditEventPublisher — emit audit records at-least-once
GovernancePolicy   — resolve masking/retention/classification per field/table
LineageEmitter     — publish OpenLineage-shaped lineage events
ObservabilityHook  — the single observability seam (counter, gauge, span, log)
FinOpsSink         — receive cost metrics from cloud-specific cost trackers
SecretProvider     — single seam for secret lookup
StageMetricsHook   — typed per-stage pipeline metrics (rows, latency, errors)
```

Plus the `StageMetrics` record — immutable snapshot of the three Culvert metric series (`culvert/rows_processed`, `culvert/stage_latency_ms`, `culvert/error_count`) with their fixed label schema of `pipeline_id`, `run_id`, and `stage_name`. `StageMetrics` is not a contract in the Protocol/interface sense; it is the value type that `StageMetricsHook.record_stage_metrics()` carries. I count it separately because it is semantically different from the sixteen behavioural interfaces.

The same set exists in Python, in `data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/contracts/`\index{Culvert!python contracts directory}. Python packages them differently — `source.py` holds `Source`, `Sink`, and `Transform` together; `stage_metrics.py` holds both the frozen dataclass and the hook Protocol — but the behavioural surface is identical.

```python
# data_pipeline_core/contracts/source.py (excerpt)
@runtime_checkable
class Source(Protocol[T_co]):
    """Anything that yields records into the pipeline."""
    def read(self, context: "RuntimeContext") -> Iterator[T_co]: ...

@runtime_checkable
class Sink(Protocol[U_contra]):
    """Anything that consumes records."""
    def write(self, records: Iterator[U_contra], context: "RuntimeContext") -> None: ...

@runtime_checkable
class Transform(Protocol[V, W]):
    """Anything that maps records."""
    def apply(self, records: Iterator[V], context: "RuntimeContext") -> Iterator[W]: ...
```

```java
// contracts/Source.java (excerpt)
@FunctionalInterface
public interface Source<T> {
    /** Stream records into the pipeline. Must be lazy — do not materialise. */
    Iterator<T> read(RuntimeContext context);
}
```

The Java interface and the Python Protocol describe the same contract. An implementation that satisfies one will satisfy the other in any polyglot pipeline that crosses the language boundary.

## The seam in practice

`BlobStore` is the contract that illustrates the seam most clearly.\index{BlobStore}

```python
# data_pipeline_core/contracts/blob_store.py
class BlobStore(Protocol):
    """Object storage abstraction. URIs are opaque strings."""
    def get(self, uri: str) -> bytes: ...
    def open(self, uri: str, mode: str = "rb") -> BinaryIO: ...
    def put(self, uri: str, data: bytes) -> None: ...
    def list(self, prefix: str) -> Iterator[str]: ...
    def exists(self, uri: str) -> bool: ...
    def delete(self, uri: str) -> None: ...
    def copy(self, src: str, dst: str) -> None: ...
```

GCP implementation: `data_pipeline_gcp_gcs.GCSBlobStore` — a thin wrapper around `google.cloud.storage.Client`. Hypothetical AWS implementation: `data_pipeline_aws_s3.S3BlobStore`. Hypothetical Azure implementation: `data_pipeline_azure_adls.ADLSBlobStore`. The Java reactor has the same contract at `com.enrichmeai.culvert.contracts.BlobStore`\index{BlobStore!Java interface}, with the same seven methods.

The HDR/TRL parser, which used to sniff `gs://` from the URI and talk directly to GCS, now takes a `BlobStore` and calls `blob_store.open(uri)`. The parser does not care what scheme the URI has. That one dependency-inversion eliminates the parser's GCP coupling entirely.

`JobControlRepository` is the contract that illustrates the depth of the cloud-specific work.\index{JobControlRepository} The GCP implementation, `BigQueryJobControlRepository`, has 49 BigQuery references across 511 lines — it builds parameterised SQL, manages partitioned tables, handles retry bookkeeping, and keeps the job ledger consistent under concurrent Dataflow workers. That is the right amount of BigQuery for a BigQuery-backed job ledger. A DynamoDB implementation would do the equivalent amount of DynamoDB work. The contract does not know and does not care.

## Holding the boundary

The boundary is enforced. Not by a shell-script grep in CI — but by compiled assertions baked into the Java unit-test suite itself. In `BudgetGovernancePolicyTest` and `PiiMaskingGovernancePolicyTest`, AssertJ assertions walk the source of every class in `data-pipeline-core-java` and fail the build if any import line contains `com.google.cloud` or `org.apache.beam`\index{cloud-neutral contracts!test enforcement}:

```java
// BudgetGovernancePolicyTest.java (line ~278)
assertThat(importLine)
    .as("BudgetGovernancePolicy must not import com.google.cloud.*")
    .doesNotContain("com.google.cloud");
```

The Python side is simpler: a grep against the contracts package returns zero matches on `google.cloud`. I have checked this; the number is zero
(`data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/contracts/` has no GCP imports).

This is the same trick Spring projects have used for two decades to keep their kernels honest — make the boundary machine-checkable, not a convention people hope everyone remembers.

## What the contracts do not include

`RuntimeContext` is the framework's `ApplicationContext`\index{RuntimeContext} — it carries `run_id`, `environment`, `config`, `secrets`, `observability`, `lineage`, `finops`, and `governance`, and it provides a `get(protocol)` / `register(protocol, impl)` pair that amounts to a one-method dependency-injection container. It is constructed once per pipeline execution by the bootstrap routine, populated by each cloud module's `auto_config()` callable, and threaded through every component invocation. A pipeline author never constructs a `BigQueryWarehouse` directly; they call `context.get(Warehouse)` and the auto-config machinery has already wired the right implementation in.

The contracts do not include anything about *scheduling*. A `Pipeline` knows its name, its stages, and how to validate its own graph. It does not know whether it runs on Composer, Step Functions, or a local in-process runner — that is the orchestration module's job, handled in the GCP case by `data-pipeline-gcp-composer` compiling the cloud-neutral DAG model into Airflow operators. Chapter 11 covers that in detail.

The contracts also do not include anything about *format*. A `Source[bytes]` might be yielding CSV, fixed-width, Avro, or Parquet. The parser is a separate concern — typically a `Transform[bytes, Mapping[str, Any]]` wrapping the HDR/TRL parser or an Avro decoder. Format-awareness belongs at the stage boundary, not the storage boundary.

## What is shipped and what is not

The Java reactor is at `0.1.0` (`data-pipeline-libraries-java/pom.xml`). The sixteen contracts compile, the GCP adapter modules compile, the integration test tier passes against Testcontainers emulators. This is built and frozen.\index{Culvert!java-0.1.0}

What is not shipped: the coordinated Maven Central + PyPI release. Publishing the Java artifact as `com.enrichmeai.culvert:data-pipeline-core-java:0.1.0` to Maven Central, and publishing the Python adapter modules to PyPI under the `culvert-*` names, requires the coordinated release process described in Chapter 17. The `culvert` PyPI name is reserved; the `culvert-*` names are reserved. The current PyPI distributions are still `data-pipeline-core`, `data-pipeline-gcp-bigquery`, `data-pipeline-gcp-gcs`, and `data-pipeline-gcp-pubsub`. That is the honest status, and it matters: nothing in the code changes when the coordinated release lands. The contracts are the contracts. The adapters are the adapters. The release is an act of publication, not an act of engineering.

\begin{takeaways}
**Chapter 4 — key points**

- Culvert was GCP-first by necessity and cloud-neutral by design: the audit
  found roughly half the codebase had zero `google.cloud` dependencies despite
  living under a `gcp_pipeline_*` namespace.
- The Spring precedent is the instructive one: `spring-core` was never
  contaminated with relational assumptions even when JPA was the only
  implementation. Culvert's core carries no GCP imports even though GCP is the
  only full implementation today.
- Sixteen behavioural interfaces (`Source`, `Sink`, `Transform`, `Pipeline`,
  `PipelineStage`, `RuntimeContext`, `JobControlRepository`, `BlobStore`,
  `Warehouse`, `AuditEventPublisher`, `GovernancePolicy`, `LineageEmitter`,
  `ObservabilityHook`, `FinOpsSink`, `SecretProvider`, `StageMetricsHook`)
  plus the `StageMetrics` value record define the entire framework-to-cloud
  seam. They live in the contracts packages of both the Java reactor
  (`com.enrichmeai.culvert.contracts`) and the Python core
  (`data_pipeline_core.contracts`).
- The boundary is machine-enforced: AssertJ assertions in the Java unit suite
  fail the build on any `com.google.cloud.*` import in core; the Python
  contracts package is clean by grep.
- The Java reactor is frozen at `0.1.0`. The coordinated Maven Central + PyPI
  `culvert` release is ahead; current Python distributions remain
  `data-pipeline-*` until that release lands.
\end{takeaways}

\newpage

# Chapter 5 — The Contract Set

I said in the previous chapter that the framework's relationship with the cloud lives entirely in its contracts. Let me be more precise than that, because I have a habit of writing from memory and then discovering that memory is wrong in exactly the ways that flatter the speaker.

The v1 manuscript — the raw GCP-origin memoir that became this book — describes "roughly a dozen Python protocols." Roughly a dozen is wrong. There are sixteen, and I have now gone and counted them properly, because the reader deserves better than a confident miscount. While I was at it, I also wrote about `Warehouse` having five methods. It has six. The one I dropped from memory is `copy` — the server-side table clone that BigQuery executes as a metadata operation and Snowflake serves as a `CLONE`. It is not the interesting one, which is precisely why I forgot it.

I am telling you this not to flag my own limitations (though there is that), but because the drift between what a design *feels like* and what it *actually is* turns out to be exactly the kind of thing the contracts prevent in the codebase itself. The contract is the memory you cannot argue with. Write it down, with types. If my prose summary of the surface diverges from the interface, the interface is right.

So: sixteen interfaces, one value type. Here is the real surface.

---

## Storage and I/O

Three contracts handle how data moves in and out of the pipeline. They sit at different levels of abstraction and they compose in a single natural pattern: a stage reads from a `Source`, optionally bounces intermediate objects through a `BlobStore`, and writes to a `Sink`. The stage never imports anything from a cloud module. The `RuntimeContext` carries the concrete implementations.

| Contract | Java | Python | Core methods |
|---|---|---|---|
| `BlobStore` | `BlobStore.java:18` | `blob_store.py:16` | `get`, `put`, `openInput`, `openOutput`, `list`, `exists`, `delete`, `copy` |
| `Source<T>` | `Source.java:19` | `source.py:38` | `read(context)` |
| `Sink<U>` | `Sink.java:16` | `source.py:42` | `write(records, context)` |

(`data-pipeline-libraries-java/data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/`)
(`data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/contracts/`)

### BlobStore

`BlobStore`\index{BlobStore} is the lowest-level storage primitive. Eight methods: two bulk-transfer ones (`get` returns bytes, `put` overwrites); two streaming alternatives for large objects (`openInput` and `openOutput`, both caller-closes); `list` which yields URIs under a prefix in lexicographic order, returning an `Iterator<String>` rather than materialising the whole listing; and `exists`, `delete`, and `copy`. [`data-pipeline-libraries-java/data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/BlobStore.java:18`]

The thing that keeps `BlobStore` cloud-neutral is not what it does — it is what it refuses to do. The framework never parses URIs. A `gs://bucket/path` is an opaque string; the GCS adapter knows what to do with it. The Javadoc at line 59 explicitly states that cross-store copies (`gs://` to `s3://`) are out of scope: implementations may throw `UnsupportedOperationException` for foreign schemes. The boundary is documented, not just assumed.

Python reflects the same contract at [`data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/contracts/blob_store.py:16`], decorated `@runtime_checkable` so that `isinstance(impl, BlobStore)` works in tests without inheritance.

### Source\<T\> and Sink\<U\>

`Source<T>` is a single-method contract: `read(context)` returns a lazy `Iterator<T>`. The `@FunctionalInterface` annotation in Java is intentional — any lambda that accepts a `RuntimeContext` and returns an iterator qualifies. The Javadoc is explicit that `read` must be lazy: implementations must not materialise the full result in memory. That constraint propagates to every adapter. [`data-pipeline-libraries-java/data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/Source.java:19`]

`Sink<U>` is the mirror: `write(records, context)` consumes the iterator. Also a `@FunctionalInterface`. Also lazy by expectation. Both live as Protocols in [`data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/contracts/source.py`] — Python can express covariant type variables that Java cannot, which is occasionally useful and never a source of confusion. [`data-pipeline-libraries-java/data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/Sink.java:16`]

---

## Compute and pipeline composition

Four contracts describe what a pipeline *is* and what it *does*. They say nothing about scheduling or execution — that belongs to the orchestration layer.

| Contract | Java | Python | Core methods |
|---|---|---|---|
| `Warehouse` | `Warehouse.java:24` | `warehouse.py:25` | `query`, `execute`, `loadFromUri`, `merge`, `copy`, `tableExists` |
| `Pipeline` | `Pipeline.java:15` | `pipeline.py:19` | `name()`, `stages()`, `validate()` |
| `PipelineStage` | `PipelineStage.java:14` | `pipeline.py:28` | `name`, `inputs`, `outputs`, `execute(context)` |
| `Transform<V,W>` | `Transform.java:16` | `source.py:52` | `apply(records, context)` |

### Warehouse

`Warehouse`\index{Warehouse} is the tabular complement to `BlobStore`. Six operations — `query` (SELECT), `execute` (DML/DDL), `loadFromUri` (bulk load from blob storage), `merge` (standard upsert), `copy` (table clone), and `tableExists`. [`data-pipeline-libraries-java/data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/Warehouse.java:24`]

The Javadoc at line 11 states the design constraint plainly: cloud-specific capabilities — BigQuery partitioning, Redshift sort keys, Snowflake clustering, Synapse distribution — do not appear on this interface. They live on cloud-specific extension classes in the cloud module. The reason is not philosophy. The reason is that putting BigQuery idioms on the shared interface breaks every non-GCP adapter immediately.

`fqtn` (fully-qualified table name) is, like all URIs in this framework, an opaque string. BigQuery parses it as `project.dataset.table`; Redshift and Snowflake parse it as `database.schema.table`. The contract specifies the convention; the implementation does the parsing. `loadFromUri` bridges `BlobStore` and `Warehouse`: hand it a blob URI and a target table and the warehouse arranges the bulk load. GCP's BigQuery does this in a `LoadJob`; Redshift does it with a `COPY ... FROM ... IAM_ROLE` statement. The call-site is identical in both cases — the protocol does not care which one fires.

A worked example, because the abstract version is hard to argue with and hard to evaluate. Here is what the `Warehouse` protocol looks like stripped to its real surface — and note the six methods, not five:

```python
# data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/contracts/warehouse.py:25
class Warehouse(Protocol):
    def query(self, sql: str, params=None) -> Iterator[Mapping[str, Any]]: ...
    def execute(self, sql: str, params=None) -> None: ...
    def load_from_uri(self, uri: str, target_table: str,
                      schema: EntitySchema) -> int: ...
    def merge(self, source_table: str, target_table: str,
              keys: List[str]) -> int: ...
    def copy(self, source_table: str, target_table: str) -> int: ...
    def table_exists(self, fqtn: str) -> bool: ...
```

The GCP implementation lives in `data-pipeline-gcp-bigquery`. A hypothetical AWS implementation would live in `data-pipeline-aws-redshift` and look something like this:

```python
class RedshiftWarehouse:
    def __init__(self, conn: redshift_connector.Connection):
        self._conn = conn

    def query(self, sql, params=None):
        cur = self._conn.cursor()
        cur.execute(sql, params or {})
        cols = [d[0] for d in cur.description]
        for row in cur:
            yield dict(zip(cols, row))

    def load_from_uri(self, uri, target_table, schema):
        copy_sql = f"COPY {target_table} FROM '{uri}' IAM_ROLE ... FORMAT CSV"
        cur = self._conn.cursor()
        cur.execute(copy_sql)
        return cur.rowcount
    # ...
```

These are different. The first one talks to BigQuery; the second one talks to Redshift. The protocol does not care. The pipeline code that calls `context.get(Warehouse).load_from_uri(...)` does not care. The decision about which `Warehouse` is in the runtime context is made once, at bootstrap, by whichever `culvert-*` cloud package the user has installed. That is the entire trick. Spring did this in 2003. We are not inventing anything.

### Pipeline and PipelineStage

`Pipeline` and `PipelineStage` are the composition contracts. `Pipeline` has three methods: `name()` returns a unique string identifier; `stages()` returns the ordered list of `PipelineStage` objects; `validate()` checks the graph — no orphan inputs, no cycles, every stage's declared inputs are produced by an earlier stage — and raises `IllegalStateException` if the pipeline cannot run. [`data-pipeline-libraries-java/data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/Pipeline.java:15`]

`PipelineStage` carries four items: `name()`, `inputs()` (a list of upstream stage names), `outputs()` (a list of logical output names downstream stages reference), and `execute(context)`. The dependency edges are declared by string name, not by object reference. That keeps the graph data-serialisable: a Composer DAG renderer can read a `Pipeline` object and produce Airflow task dependency declarations without instantiating the stage implementations. [`data-pipeline-libraries-java/data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/PipelineStage.java:14`]

Both live in [`data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/contracts/pipeline.py:19`].

### Transform\<V, W\>

`Transform<V, W>` maps a stream of V records to a stream of W records via `apply(records, context)`, returning a lazy `Iterator<W>`. Like `Source` and `Sink` it is a `@FunctionalInterface`. The Javadoc notes that transforms should be pure where possible. The Python equivalent lives at [`data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/contracts/source.py:52`]. [`data-pipeline-libraries-java/data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/Transform.java:16`]

`Transform` is the workhorse for field-level logic: type coercion, enrichment, PII redaction. A masking transform reads the `GovernancePolicy` from the `RuntimeContext`, applies the field masking rules, and emits sanitised records — without ever importing a cloud SDK.

---

## Operational seams

Six contracts cover the runtime concerns. They are the instruments by which the framework is observable, auditable, governable, and self-aware.

| Contract | Java | Python | Core methods |
|---|---|---|---|
| `JobControlRepository` | `JobControlRepository.java:25` | `job_control.py:27` | 11 methods (lifecycle + query + cost) |
| `ObservabilityHook` | `ObservabilityHook.java:20` | `observability.py:26` | `counter`, `gauge`, `histogram`, `log`, `span` |
| `StageMetricsHook` | `StageMetricsHook.java:32` | `stage_metrics.py:71` | `recordStageMetrics(metrics)` |
| `LineageEmitter` | `LineageEmitter.java:16` | `lineage.py:17` | `emit(event)` |
| `AuditEventPublisher` | `AuditEventPublisher.java:15` | `audit.py:17` | `publish(record)`, `flush()` |
| `GovernancePolicy` | `GovernancePolicy.java:20` | `governance.py:21` | `classify`, `maskingFor`, `retentionFor` |

### JobControlRepository

`JobControlRepository`\index{JobControlRepository} is the pipeline-job state machine. Every pipeline run is a row in a ledger; this contract describes the full CRUD on that ledger. [`data-pipeline-libraries-java/data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/JobControlRepository.java:25`]

Eleven methods. `createJob` inserts a new row in `CREATED` state. `updateStatus` advances the state machine. `markFailed` records structured error context including a URI to quarantined records. `markRetrying` bumps the retry counter. `cleanupPartialLoad` deletes partial rows before a retry attempt. The query side: `getJob` by run ID; `getPendingJobs` by system; `getEntityStatus` for orchestration gating; `getFailedJobs` for operator dashboards; `getFdpJobStatus` for FDP model tracking. And `updateCostMetrics`, which attaches cost figures to the job row after compute completes. That is the actual eleven — I am counting rather than claiming a round number.

The Javadoc at line 22 notes that implementations must be transactional within a single `runId`. That constraint is enforced by the backing store, not by the contract itself, but callers can rely on the guarantee. Python mirrors all eleven at [`data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/contracts/job_control.py:27`].

### ObservabilityHook

`ObservabilityHook`\index{ObservabilityHook} is the framework's single observability seam. Metrics, structured logs, and distributed traces all flow through this one interface. Three concerns, one dependency to inject. [`data-pipeline-libraries-java/data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/ObservabilityHook.java:20`]

Five methods: `counter(name, value, tags)` increments a monotonic counter; `gauge(name, value, tags)` sets a current value; `histogram(name, value, tags)` records a distribution sample; `log(level, message, fields)` emits a structured log line; `span(name)` opens an `AutoCloseable` tracing span. The nested `Span` interface carries `setAttribute` and `recordException`, and implements `AutoCloseable` so try-with-resources works cleanly.

The consolidation was deliberate. The earlier code had `MetricsCollector` for counters and gauges, `StructuredLogger` for logs, and OTEL helpers for traces. Keeping them separate meant every stage needed three injected dependencies and the first thing you forgot was the structured logger. A `CompositeObservabilityHook` can delegate to all three backends. Tags follow OpenTelemetry attribute conventions — string keys, string values. The Python contract at [`data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/contracts/observability.py:26`] reflects the same five methods; `span` returns an `AbstractContextManager` rather than a custom interface, which fits Python idioms without losing the contract guarantee.

### StageMetricsHook and StageMetrics

`StageMetricsHook` is a narrower, Culvert-specific companion to `ObservabilityHook`. Its single method is `recordStageMetrics(metrics)`, where `metrics` is a `StageMetrics` value. [`data-pipeline-libraries-java/data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/StageMetricsHook.java:32`]

`StageMetrics`\index{StageMetrics} is the companion value type — not a contract itself (no implementation is expected to implement it), but an immutable snapshot that the contract passes. In Java it is a `record`; in Python a `frozen=True` dataclass. Three label dimensions: `pipelineId`, `runId`, `stageName`. Three metric values: `rowsProcessed` (metric `culvert/rows_processed`, CUMULATIVE INT64), `stageLatencyMs` (metric `culvert/stage_latency_ms`, GAUGE DOUBLE), `errorCount` (metric `culvert/error_count`, CUMULATIVE INT64). Both enforce non-null labels in the constructor. [`data-pipeline-libraries-java/data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/StageMetrics.java:26`] [`data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/contracts/stage_metrics.py:32`]

Why a separate interface rather than three calls to `ObservabilityHook`? Because `ObservabilityHook` is a general-purpose surface — arbitrary name, arbitrary tags. The `StageMetricsHook` codifies the Culvert-specific semantic: one call per stage completion, three fixed metric series, a fixed label schema. It makes it structurally impossible to mis-name a metric or accidentally omit a label. The Javadoc at line 14 explains this directly, and I think it is one of the better small design decisions in the framework.

### LineageEmitter

`LineageEmitter` is as small as a contract gets: a single method, `emit(event)`, where `event` is a `LineageEvent`. The `@FunctionalInterface` annotation means any lambda that accepts a `LineageEvent` qualifies. [`data-pipeline-libraries-java/data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/LineageEmitter.java:16`]

`LineageEvent` carries the four OpenLineage-shaped sub-structures: source, destination, pipeline, and audit metadata. GCP's adapter routes to Cloud Data Catalog / Dataplex; a cloud-neutral implementation targets a Marquez or OpenLineage Proxy endpoint. The Python protocol at [`data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/contracts/lineage.py:17`] is structurally identical: one `emit(event)` method.

### AuditEventPublisher

`AuditEventPublisher` publishes `AuditRecord` values with at-least-once delivery semantics. Two methods: `publish(record)` may buffer for throughput; `flush()` blocks until all buffered records have been acknowledged by the backing event bus. `flush()` is idempotent — calling it on an empty buffer is a no-op. The framework calls `flush()` at pipeline-stage boundaries and at shutdown, so the publisher never silently drops records. [`data-pipeline-libraries-java/data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/AuditEventPublisher.java:15`]

The separation from `ObservabilityHook` is deliberate. Audit records have compliance requirements — at-least-once delivery, idempotent flush, durable backing store — that do not apply to metrics or logs. Conflating them would either weaken the audit guarantees or impose unnecessary complexity on metrics implementations. You do not want your counter-increment to trigger a Pub/Sub flush. Python at [`data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/contracts/audit.py:17`].

### GovernancePolicy

`GovernancePolicy` answers three questions about any field or table: what is its sensitivity classification, what masking applies, and what retention policy applies. `classify(field, table)` returns a `DataClassification` enum value, defaulting to `INTERNAL` and never throwing. `maskingFor(field, table)` returns an `Optional<MaskingPolicy>`, empty if no masking applies. `retentionFor(table)` returns an `Optional<RetentionPolicy>`, empty for indefinite retention. [`data-pipeline-libraries-java/data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/GovernancePolicy.java:20`]

The default implementation — `StaticGovernancePolicy`, added in Stage 3 — reads a YAML file and requires no cloud service. That makes governance testable without credentials, which matters more than it sounds. The Python protocol at [`data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/contracts/governance.py:21`] reflects the same three methods using snake_case (`masking_for`, `retention_for`).

---

## Configuration and dependency injection

Three contracts handle what the pipeline needs before it can run: credentials, cost attribution, and the context object that wires everything together.

| Contract | Java | Python | Core methods |
|---|---|---|---|
| `SecretProvider` | `SecretProvider.java:18` | `secrets.py:18` | `get(name, version)` |
| `FinOpsSink` | `FinOpsSink.java:16` | `finops.py:23` | `record(metrics, tags)` |
| `RuntimeContext` | `RuntimeContext.java:33` | `runtime.py:38` | `runId()`, `environment()`, `config()`, named accessors, `get(type)`, `register(type, impl)` |

### SecretProvider — the side-by-side

`SecretProvider` is the simplest contract to reason about and the one that most clearly exposes the language-specific idiom difference in the set. There is one method. In Java you need two overloads to express a default argument; in Python you need one method with a default parameter. Both compile to the same semantic. Here is the full surface in both languages:

**Java** [`data-pipeline-libraries-java/data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/SecretProvider.java:18`]:

```java
@FunctionalInterface
public interface SecretProvider {

    /**
     * Return the secret value at {@code name}.
     *
     * Implementations should never log the returned value, even at DEBUG level.
     *
     * @throws java.util.NoSuchElementException if the secret does not exist.
     */
    String get(String name, String version);

    /** Convenience: fetch the {@code "latest"} version. */
    default String get(String name) {
        return get(name, "latest");
    }
}
```

**Python** [`data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/contracts/secrets.py:18`]:

```python
@runtime_checkable
class SecretProvider(Protocol):
    """Look up secrets by name. Implementations call Secret Manager,
    AWS Secrets Manager, Azure Key Vault, HashiCorp Vault, or just
    read from the environment.
    """

    def get(self, name: str, version: str = "latest") -> str:
        """Return the secret value at `name` (and optional `version`).

        Raises KeyError if the secret does not exist. Implementations
        should never log the returned value, even at DEBUG level.
        """
        ...
```

Same contract. The error type differs — Java throws `NoSuchElementException`, Python raises `KeyError` — because those are the idiomatic choices in each language for a missing key. The prohibition on logging the returned value appears in both docstrings in identical terms. Implementations range from GCP Secret Manager to AWS Secrets Manager, Azure Key Vault, HashiCorp Vault, or plain environment variables. The protocol does not care which one fires at runtime.

### FinOpsSink

`FinOpsSink` receives cost metrics from cloud-specific cost trackers and persists them wherever the team aggregates cost data. `record(metrics, tags)` is the single method. `CostMetrics` carries the numeric figures (estimated USD, billed bytes scanned, billed bytes written); `FinOpsTag` carries the attribution dimensions (pipeline name, stage name, system ID, environment). [`data-pipeline-libraries-java/data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/FinOpsSink.java:16`]

The Javadoc at line 12 explains the explicit-tags decision: `FinOpsTag` is passed directly rather than read from the `RuntimeContext`. Cost emissions are infrequent and lossy attribution is the most common bug in cost-tracking systems. Making attribution tags explicit in the method signature makes the data flow visible and keeps attribution from silently disappearing if a context is mis-wired. Python at [`data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/contracts/finops.py:23`].

### RuntimeContext

`RuntimeContext`\index{RuntimeContext} is the framework's dependency-injection container. It is not a factory or a registry in the traditional IoC sense; it is the object that every stage method receives, carrying both configuration data and pointers to all the registered contract implementations. [`data-pipeline-libraries-java/data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/RuntimeContext.java:33`]

Three categories of member. Identity and configuration: `runId()`, `pipelineId()`, `environment()`, `config()`. Named accessors for each registered contract: `secrets()`, `observability()`, `stageMetrics()`, `lineage()`, `finops()`, `governance()`. And the generic registry: `get(Class<T> protocolType)` and `register(Class<T> protocolType, T impl)`.

The `get` and `register` methods are the extension points. The framework's auto-config bootstrap calls `register` for each contract that an installed cloud module provides. Test code calls `register` to inject mocks. A stage that needs a `BlobStore` calls `context.get(BlobStore.class)` and gets back whatever the runtime has registered — GCS in production, an in-memory fake in unit tests. Change the cloud by changing which module is on the classpath. The stage code is untouched.

The Python protocol at [`data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/contracts/runtime.py:38`] reflects the same structure with one extra note in the module docstring at line 17: when a `RuntimeContext` crosses a distributed compute boundary — a Beam worker, for example — only `run_id`, `environment`, and `config` serialise. The registry is transient and is rebuilt worker-side by the auto-config mechanism. That constraint belongs on the concrete implementation, not the contract, but the Python module docstring flags it explicitly so implementors know it is coming.

---

## How the families compose

The four families are not isolated; `RuntimeContext` is the thread that stitches them together. A typical stage touch-point: `PipelineStage.execute(context)` is the entry point. The stage calls `context.get(BlobStore.class)` to retrieve its source storage, `context.get(Warehouse.class)` to reach its target table, `context.observability().counter(...)` to emit metrics, and `context.lineage().emit(...)` to publish a lineage event. Nothing imported from a cloud module. By the time the stage returns, the ledger row is updated via `JobControlRepository`, the lineage event is queued, the audit record is buffered for the next `flush()`, and the stage metrics — via `StageMetricsHook` and its typed `StageMetrics` value — are on their way to wherever the team has registered them to go.

That is the surface. Nothing else in the framework talks to a cloud SDK directly. If you find yourself reaching for `from google.cloud import bigquery` in a file that does not live under a `culvert-gcp-*` module, you have made a mistake and the CI grep check will tell you so.

---

\begin{takeaways}
**The sixteen contracts and one value type**

The contracts are: `BlobStore`, `Source<T>`, `Sink<U>` (storage/I-O); `Warehouse`, `Pipeline`, `PipelineStage`, `Transform<V,W>` (compute/pipeline); `JobControlRepository`, `ObservabilityHook`, `StageMetricsHook`, `LineageEmitter`, `AuditEventPublisher`, `GovernancePolicy` (operational seams); `SecretProvider`, `FinOpsSink`, `RuntimeContext` (configuration/DI). `StageMetrics` is the companion value type, not a contract. All sixteen Java interfaces are in `data-pipeline-libraries-java/data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/`; all sixteen Python Protocols are in `data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/contracts/`. The Java reactor is built and frozen at `java-0.1.0`; the Python Protocols exist and are `@runtime_checkable`; neither is yet published to Maven Central or PyPI.

**The design rules that keep them cloud-neutral**

URIs are opaque strings. The framework never parses them. Cloud-specific features (BigQuery partitioning, Redshift sort keys) go on cloud-specific extension classes, not on the shared interface. `RuntimeContext` carries the registry; stages call `context.get(ContractType.class)` and never import a cloud SDK. The one exception is `ObservabilityHook`'s nested `Span` — a handle type, not a seam. Audit and observability are separate contracts because they have different delivery guarantees.

**The memory-vs-reality check**

The v1 manuscript said "roughly a dozen protocols." There are sixteen. It showed `Warehouse` with five methods. There are six — `copy` is the one that does not announce itself. The contracts are the corrective: write the interface down, with types, and the surface is what the types say it is, not what you remember.
\end{takeaways}

\newpage

# Chapter 6 — Polyglot by Design

The question I get most often, when I explain Culvert to another engineer, is
some variant of: *why two languages?* Why not pick one, do it properly, and
stop making life complicated for people who have to maintain both sides of the
seam?

It is a fair question, and it deserves an honest answer rather than the usual
defensive mumble about ecosystem maturity. The honest answer is that Java and
Python are not in competition here. They own genuinely different layers of the
problem, and the boundary between those layers is load-bearing, not
cosmetic. Understanding where the seam falls — and why it falls there — is what
this chapter is about.

## Why two languages at all

Let me start with a small confession. The framework did not begin polyglot by
design. It began as a Python project, because the data engineering world lives
in Python. DAGs, transforms, dbt macros — if you are writing data pipelines in
2024, the tooling ecosystem hands you Python. You do not fight that.

The complication arrived when we looked seriously at execution. Apache Beam's
Python SDK exists and is capable; we used it. But the moment you run real
production workloads on Dataflow at any meaningful volume, you discover that
the Java SDK is where Beam's authors live. The connector coverage is wider, the
runner integration is tighter, and — critically — the failure modes are better
documented because more people are hitting them in anger on Java. We did not
*choose* Java for Dataflow. We arrived at it empirically, the way you arrive at
a life decision you did not plan to make: gradually, then all at once.

Once Java was doing the execution work, the question became where to draw the
line. Everything I have ever learned about system design says: draw the line at
a stable interface, make that interface explicit, and then stop caring which
side of the interface a given piece of code lives on. That is what the Culvert
contracts are. The language boundary and the contract boundary are the same
line, by design.

## The division of labour

The authoritative statement of how the two runtimes divide the work is in
`docs/framework-evolution/13-python-parity-release.md` (lines 20–25). I will
quote it directly rather than paraphrase it, because the table in that document
is the decision record, not this chapter.

| Layer | Strategy | Why |
|---|---|---|
| **Contracts** | **Both** implement the same spec | `docs/CONTRACT.md` is language-neutral. Java: 16 contract interfaces + the `StageMetrics` record. Python now matches after Wave A (`StageMetrics`/`StageMetricsHook` added in `data-pipeline-core/contracts/`). |
| **dbt / transform** | **Reuse** (language-neutral) | It is SQL and macros, not Java or Python. `data-pipeline-transform` is Python-packaged but the assets are dbt; there is deliberately no Java transform module. |
| **Dataflow / execution** | **Java** (Beam) | `data-pipeline-gcp-dataflow-java`: `DataflowPipeline` + `StageTransform`. The legacy Python Beam path is not being ported. |
| **Orchestration** | **Reuse** — complementary, not duplicate | Python owns the runtime side (`operators/`, `sensors/`, `hooks/`, `routing/`, `factories/`); Java owns the cloud-neutral model and renderers (`DagSpec`/`TaskSpec`, `AirflowDagRenderer`/`ComposerDagRenderer`). |

That table is the design. Everything else in this chapter is commentary on why
those four rows are the right rows.

### Contracts: both languages, one spec

The contracts layer is the reason a polyglot framework is even coherent. If
Java and Python had different contract shapes — different method names, different
signatures, different invariants — you would not have a framework. You would
have two frameworks that happened to talk to the same cloud.

`docs/CONTRACT.md` is language-neutral. It specifies the contracts as
behavioural descriptions, not as Java interfaces or Python Protocols. Java then
implements those as interfaces in `data-pipeline-core-java`; Python implements
them as Protocol classes in `data-pipeline-core`. The reconciliation of the
Python side against the final Java contracts was Wave A of the parity epic
(PR #113, merged to `main`). Before that, the Python contracts had accrued
drift — `BlobStore.open()` was unsigned in a way that the Java interface's
`openStream()` was not, `RuntimeContext` was missing `pipeline_id`. The Wave A
work fixed that drift systematically, added `StageMetrics` and
`StageMetricsHook` to both sides, and produced a short conformance note per
contract. The starting point for this chapter, therefore, is a contract set
that is actually in sync — not aspirationally in sync, actually in sync.

This matters for one practical reason: a contract that exists only in one
language is a trap waiting to spring. The Java side gets the better connector
or the faster implementation; Python users watch enviously. Or the Python side
evolves because it is nimbler, and the Java side falls behind. The only way to
prevent both failure modes is to make the contract the authority, not either
implementation, and to run the contract-test harness against both. That is what
`data-pipeline-contract-tests` and `data-pipeline-contract-tests-java` do.

### dbt / transform: language-neutral reuse

The transform layer is the simplest case in the table. dbt models and macros
are SQL. SQL does not belong to Java or Python. The assets in
`data-pipeline-transform` — `pii_masking.sql`, `enrichment.sql`, and the
surrounding macro infrastructure — are dbt, full stop. They are Python-packaged
because dbt is Python, but they contain no Python logic. A Java pipeline can
trigger them via a dbt CLI invocation; a Python pipeline can import the macro
package directly. The point is that neither language *owns* the transform
layer. You use it from whatever side you happen to be standing on.

This is one of those cases where "reuse" is not a design goal in itself. It is
simply what you arrive at when you recognise that a piece of the stack is
already cloud-neutral and already language-neutral, and you resist the urge to
wrap it in something that is neither.

### Dataflow / execution: firmly Java

This is where I will be direct about something that is not a design choice but
a pragmatic verdict. The Python Beam execution path is not being ported. The
decision is in the table: "Legacy Python Beam is not being ported."

I am aware that this will strike some readers as a betrayal of the polyglot
premise. It is not. The polyglot premise says that the layer *above* execution
— the contract layer — is language-neutral. It does not say that every cloud
execution engine must be wrapped in every language. Apache Beam's Dataflow
runner on Java is the mature, production-validated path. `DataflowPipeline`
(`data-pipeline-gcp-dataflow-java`, `DataflowPipeline.java:1`) bridges
Culvert's topology contract to Apache Beam's runner; `StageTransform`
(`StageTransform.java:1`) bridges each `PipelineStage` to a Beam `PTransform`.
Those two classes are the execution seam. They depend on the contract
interfaces, and the contracts are language-neutral. If someone builds
`culvert-aws-emr-java` using the same contract interface, the Python side does
not need to change at all.

The practical consequence for a pipeline author is straightforward: write your
business logic against the Python contracts; the Dataflow execution happens in
the Java runtime, invisibly, coordinated through the DAG. You do not write
Beam. You write Culvert stages.

### Orchestration: complementary, not duplicate

Orchestration is the most interesting case in the table because it looks, on
the surface, like duplication. Python has an orchestration module
(`data-pipeline-orchestration`). Java has an orchestration module
(`data-pipeline-orchestration-java`). Surely one of those is redundant?

They are not, and understanding why requires distinguishing between two things
that people often conflate: the *model* of a DAG and the *runtime* of a DAG.

The Java side owns the model. `DagSpec`
(`data-pipeline-orchestration-java/src/main/java/com/enrichmeai/culvert/orchestration/DagSpec.java:1`)
is "an immutable, scheduler-agnostic description of a directed acyclic graph"
— its own Javadoc says so. It captures dag ID, schedule, tasks in topological
order, and edges, without importing any Airflow or Composer library.
`TaskSpec` (`TaskSpec.java`) is the per-stage node. `PipelineToDagSpec`
(`PipelineToDagSpec.java`) converts a `Pipeline` contract implementation into
a `DagSpec`. The renderers — `AirflowDagRenderer` and `ComposerDagRenderer`
(`AirflowDagRenderer.java`, `ComposerDagRenderer.java`) — take a `DagSpec` and
produce the cloud-specific submission artefact. Cloud-neutral model;
cloud-specific renderers. The same Spring pattern, applied to DAG generation
rather than persistence.

The Python side owns the runtime. The `operators/` subdirectory contains the
Airflow operator implementations — the code that actually executes inside the
scheduler at run time. `sensors/` contains the Pub/Sub and Dataflow sensors
that Airflow polls between tasks. `hooks/` contains the secrets integration.
`factories/` contains the DAG factory that assembles an Airflow DAG object from
configuration at DAG-parse time. None of that is duplicating the Java model;
it is the runtime substrate that the model's output runs on.

So: Java generates the DAG description; Python executes it. You need both. The
seam between them is the `DagSpec` — a serialisable, language-neutral struct
that Java produces and Python consumes. If we ever need to port this to AWS
MWAA or Azure Data Factory, the model changes in one place (a new renderer in
Java); the Python runtime operators adapt; the pipeline authors see nothing.

## The decorator surface

I want to spend a moment on the Python decorator surface, because it is the
place where the framework is most opinionated about how it will be used, and
because there is a gap between the current state and the design direction that
I need to be honest about.

The decorators as shipped in Sprint 4 are in
`data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/decorators.py`.
The file header says it plainly: "intentionally thin: they don't impose any
base class or metaclass on the decorated target; they just tag it with metadata
attributes that the registry reads" (decorators.py:5–9). The current surface
is five decorators:

- `@pipeline(name: Optional[str])` — marks a class as a `Pipeline`
  implementation and registers it with the auto-config registry
  (decorators.py:22–38).
- `@stage(name: Optional[str])` — marks a class as a `PipelineStage`
  implementation (decorators.py:41–47).
- `@source(name: Optional[str])` — marks a class as a `Source` implementation,
  registers under `"source"` (decorators.py:50–57).
- `@sink(name: Optional[str])` — marks a class as a `Sink` implementation,
  registers under `"sink"` (decorators.py:59–65).
- `@transform(name: Optional[str])` — marks a class as a `Transform`
  implementation, registers under `"transform"` (decorators.py:68–74).

That is the entire `__all__` (decorators.py:77). Five decorators, one
parameter each — the registration name — and a thin metadata tag. This is not
all that the decorator surface will eventually be. The Sprint-3 stage design
(doc 13, §4) describes a richer surface in which `@pipeline` carries a
schedule, retry configuration, and FinOps tags; `@source` carries a URI and
schema; `@sink` carries a target and write disposition; `@transform` carries an
explicit input edge. Those richer signatures are not yet implemented. I will
not pretend they are.

What the current decorators *do* establish is the registration model. A class
decorated with `@source` becomes discoverable to the framework's auto-config
registry without the pipeline author having to write any wiring code. The
analogy to Spring's `@Component` is honest at this level: `@Component` in 2003
was also a thin marker that the container used to discover and wire beans. The
difference was that Spring then had ten years of accumulated convenience
annotations built on top of that marker. Culvert's `@pipeline` and `@source`
are at the 2003 end of that curve, not the 2013 end.

I find that the honest version of the Spring analogy is more useful than the
flattering version. The infrastructure is right. The registration model is
right. The richer ergonomics are the next wave of work, and when they land
they will land *on top of* the registration model rather than replacing it —
exactly as `@Service`, `@Repository`, and `@Autowired` landed on top of
`@Component` without replacing it.

## When to reach for Java vs Python

The question of which language to work in day-to-day is actually not very
interesting once you understand the table above. The answer falls out of the
layer you are working in.

If you are writing a new **execution adapter** — a new way to run stages on a
managed execution service — you are working in Java, against the `Pipeline` and
`PipelineStage` contracts, following the pattern established by `DataflowPipeline`
and `StageTransform`. The execution side is Java because that is where the Beam
runner and its connectors live, and I am not going to paper over that with a
thin Python wrapper that adds latency and a failure mode.

If you are writing a **pipeline** — a business process that ingests, transforms,
and loads data — you are working in Python, against the same contracts expressed
as Protocols. You decorate your classes with `@pipeline`, `@source`,
`@transform`, `@sink`; the auto-config registry discovers them; the Java
execution runtime picks them up through the DAG. The dbt macros in
`data-pipeline-transform` are available to you without importing anything
Java-flavoured.

If you are writing a new **cloud adapter** — a new `BlobStore` for a new object
store, a new `Warehouse` for a new analytics engine — you have a choice. The
Java side has the GCS and BigQuery adapters; the Python side has matching GCS
and BigQuery adapters. For a new cloud the convention is to write both, in
parallel, running the shared contract-test harness against each. The contract
tests are the definition of "done" for an adapter; if both language
implementations pass, the contract is satisfied.

If you are working on **orchestration runtime** — new operators, new sensors,
new callback handlers — you are in Python, in `data-pipeline-orchestration`. If
you are working on the **DAG model or a new renderer** — a new scheduler target
— you are in Java, in `data-pipeline-orchestration-java`. The seam is the
`DagSpec`.

If you are writing **dbt macros or SQL models** — you are in neither, you are
in SQL, and the framework is not in the room with you. Land the output in
`data-pipeline-transform`, run the dbt tests, and stop.

## Honest status

Culvert is built and held. Java is at `0.1.0` on `main`, tagged `java-0.1.0`,
frozen pending the coordinated release. It does not publish to Maven Central
alone. Python parity is in progress: Wave A (contract reconciliation, T17.1 and
T17.2, PR #113) is merged to `main`; Wave B (core depth — `DefaultRuntimeContext`,
`dataquality`, concrete governance policies, FinOps cost model, PRs #117–#120)
is in PR #123. Wave C (GCP adapter parity for secrets and observability) and
Wave D (packaging under the `culvert` name) remain open.

The release gate is explicit: Java *and* Python both ready, then a single
coordinated publish to Maven Central (`com.enrichmeai.culvert:*`) and PyPI
(`culvert`). Neither side ships alone. Nothing is published yet.
(`docs/framework-evolution/13-python-parity-release.md`, §2.)

The polyglot design is not a promise made about a future framework. It is a
description of a framework that exists and is held, waiting for the last wave
of parity work to close before it ships. The seam is real. The contracts on
both sides are in sync. The orchestration split works. The only open question is
how long Wave C and Wave D take, and that is an execution question, not a
design question.

Spring did not ship multi-database in version one. It shipped `spring-data-jpa`
first, kept `spring-core` honest about persistence, and let the MongoDB module
follow years later. The same move, applied to languages: one language-neutral
contract, one reference runtime in each language, a seam that future runtimes
can plug into. It worked in 2003. We have good reason to think it will work
here.

\begin{takeaways}
\textbf{Key takeaways}
\begin{itemize}
  \item The division of labour between Java and Python is fixed at the contract boundary, not at the organisation level. Contracts: both languages implement the same spec (\texttt{docs/CONTRACT.md} is language-neutral). dbt/transform: language-neutral reuse — it is SQL, not Java or Python. Dataflow/execution: Java only (\texttt{DataflowPipeline} + \texttt{StageTransform} in \texttt{data-pipeline-gcp-dataflow-java}). Orchestration: complementary — Java owns the cloud-neutral model (\texttt{DagSpec}, renderers); Python owns the Airflow runtime (operators, sensors, hooks, factories).
  \item The decorator surface as shipped is five thin class-level markers — \texttt{@pipeline}, \texttt{@stage}, \texttt{@source}, \texttt{@sink}, \texttt{@transform} — each taking only an optional \texttt{name} parameter (\texttt{data-pipeline-core/decorators.py}). The richer ergonomics described in the Stage-3 design (schedule, URI, schema on the decorator) are not yet implemented. The registration model is right; the convenience layer is the next wave.
  \item Orchestration is not duplicated across the two languages. Java produces the DAG description (\texttt{DagSpec}/\texttt{TaskSpec}/renderers); Python executes it (Airflow operators and sensors). The seam is \texttt{DagSpec}: immutable, serialisable, scheduler-agnostic. A new scheduler target requires a new Java renderer, not changes to the Python runtime or to any pipeline.
  \item Culvert is built and held — Java \texttt{0.1.0} frozen on \texttt{java-0.1.0}; Python Wave A merged to \texttt{main}, Wave B in PR \#123, Waves C/D open. The release gate is both languages ready, then a coordinated publish to Maven Central and PyPI (\texttt{culvert}). Nothing has published yet.
  \item Choosing Java vs Python day-to-day is not a preference question. It follows from the layer: execution adapters are Java; pipeline business logic and new contracts are Python; cloud adapters want both; orchestration runtime is Python; DAG model/renderers are Java; SQL transforms belong to neither.
\end{itemize}
\end{takeaways}

\newpage

# Without Culvert vs With It

We have spent five chapters on contracts, the contract set, and the polyglot split. Fair question at this point: what is all that abstraction actually *worth*? So let me do the thing I wish someone had done for me years ago — build the same small pipeline twice. Once the way most teams start, hand-wired straight against the cloud SDK. Once against Culvert's contracts. Same business outcome; wildly different amount of code you have to own, and — this is the part that matters — wildly different cost when something changes.

## The scenario

A file lands in object storage each morning. We need to read it, validate the rows against a schema, load the good rows into a warehouse table, and quarantine the bad ones. One entity, one job. Deliberately small, so the difference is about *shape*, not scale.

## Version A — without the framework

Straight against the GCP SDKs, the honest first draft looks like this (trimmed):

```python
from google.cloud import bigquery, storage

def ingest(uri: str) -> None:
    gcs = storage.Client()                 # bound to GCS, forever
    bq = bigquery.Client()                 # bound to BigQuery, forever
    blob = gcs.bucket(_bucket(uri)).blob(_key(uri))
    rows = list(csv.DictReader(blob.download_as_text().splitlines()))
    good, bad = [], []
    for r in rows:
        (good if _valid(r) else bad).append(r)
    bq.load_table_from_json(good, "odp.customers").result()
    if bad:
        gcs.bucket("errors").blob(f"{_run_id()}.json").upload_from_string(json.dumps(bad))
```

It works. It also *is* GCP, top to bottom. `storage.Client` and `bigquery.Client` are welded into the business logic. To unit-test it you mock the Google SDKs. To run it against a second cloud you rewrite it. To add audit, cost tracking, or a governance check you thread more SDK calls through the same function until it is six hundred lines and nobody wants to touch it. I have maintained that function on call for three years. I do not recommend it.

The cloud coupling is not a deliberate design choice here — it is a *habit*. Nobody decided the validator should know about BigQuery; it just ended up in the same file, and thin layers that are never named as thin layers become load-bearing walls.

## Version B — with Culvert

Now the same pipeline against the contracts. The business logic talks to `Source`, `Transform`, `Sink`, `Warehouse` — never to `google.cloud` anything.

```python
from data_pipeline_core.contracts.source import Source, Sink, Transform
from data_pipeline_core.contracts.runtime import RuntimeContext

class CustomerIngest(Transform):
    def apply(self, records, context: RuntimeContext):
        for r in records:
            if _valid(r):
                yield r
            else:
                context.get(Sink).write([r], context)   # quarantine sink
```

The pipeline is assembled from adapters the runtime supplies — it never names them:

```python
warehouse = context.get(Warehouse)            # BigQueryWarehouse on GCP…
warehouse.load_from_uri(uri, "odp.customers", schema)   # …RedshiftWarehouse on AWS
```

Which `Warehouse` is in the context is decided once, at bootstrap, by whichever `culvert-gcp-*` (or, one day, `culvert-aws-*`) package is installed — resolved through `AutoConfig.discover()` (Chapter [Auto-Config and Discovery]). The call site does not change. This is the same move Spring made in 2003 with `spring-data`: the abstraction hosts any implementation, and you ship the one you have.

The cross-cutting concerns you were bolting on by hand in Version A are contracts too, and they arrive the same way: `context.get(AuditEventPublisher)`, `context.finops`, `context.governance`, `context.observability`. Audit, cost, masking, tracing — call sites, not rewrites.

## The side-by-side

| | Version A (hand-wired) | Version B (Culvert) |
|---|---|---|
| Cloud coupling | GCP SDK in the business logic | none — behind `Warehouse`/`BlobStore`/`Source`/`Sink` |
| Unit test | mock `google.cloud` | supply an in-memory adapter; assert on the contract |
| Second cloud | rewrite the function | write a new adapter; call site unchanged |
| Add audit/cost/governance | thread more SDK calls | `context.get(...)` — already there |
| Who owns the plumbing | you, forever | the framework, once |

Version A is fewer lines *today*. Version B is fewer lines *over the life of the pipeline*, which is the only measurement that has ever paid off for me. The abstraction is not free — you have to learn the contracts — but it is the cheapest insurance I know against the two things that actually happen to production pipelines: the cloud bill arriving, and the business asking for the thing you did not design for.

\begin{takeaways}
\textbf{Key takeaways}
\begin{itemize}
  \item Hand-wired pipelines couple business logic to a cloud SDK by \emph{habit}, not design; those thin layers become load-bearing walls.
  \item Against Culvert, the business logic talks only to contracts (\texttt{Source}/\texttt{Sink}/\texttt{Transform}/\texttt{Warehouse}); the adapter is injected via \texttt{RuntimeContext} / \texttt{AutoConfig.discover()} and chosen once at bootstrap.
  \item Cross-cutting concerns — audit, cost, governance, tracing — are contracts reached through the context, not SDK calls threaded by hand.
  \item Version A wins on lines-of-code today; Version B wins on cost-of-change, which is the measurement that pays off over a pipeline's life.
\end{itemize}
\end{takeaways}

\newpage

# Chapter 7 — Storage and Messaging Adapters

\index{adapter|textbf}

The previous two chapters were about contracts: what they are, why they exist,
how sixteen interfaces form a portability boundary that lets you swap one cloud
for another without touching your pipeline logic. All of that is true and
useful and, if you are being honest, still a bit theoretical. Contracts are
just Java interfaces and Python Protocols. The thing that makes them real is
an adapter — the class that implements the contract against a specific cloud
SDK.

This chapter covers the first two concrete adapters in Culvert's GCP
implementation: `GcsBlobStore`, which backs `BlobStore` against Google Cloud
Storage, and `PubSubSource`/`PubSubSink`, which back `Source` and `Sink`
against Google Cloud Pub/Sub. They are the Sprint-1 and Sprint-2 deliverables
for issues #7 and #23 respectively. They are built, they are tested, and they
are sitting in the repo unpublished — exactly the honest status the framework
carries everywhere.

What I want to do in this chapter is not just show you the APIs. I want to
show you *where the cloud-specific mess lives*, because adapters are where
the clean abstractions meet the particular awkwardness of a real SDK. Each one
taught us something we had not anticipated when we wrote the contracts.

## Why adapters, not thin wrappers

There is a failure mode I have seen in almost every framework that attempts
abstraction over cloud services. The author writes the interface, then writes
a class that is essentially a one-to-one delegation to the SDK, gives it a
name ending in `Adapter`, and calls it done. What you get is an extra layer of
indirection that adds no value. The contract method calls the adapter method,
the adapter method calls the SDK method, the names are different, and you have
to trace through three files to understand what happens on a 404.

Culvert's adapters are meant to be different, and the way to be different is
to put real decisions in them. Three examples from `GcsBlobStore` alone:

1. **URI ownership.** The `BlobStore` contract (`data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/BlobStore.java:11-14`) declares URIs opaque strings. It explicitly does *not* parse them. That is a decision: the contract says what a URI conceptually is (an opaque address); the adapter decides what scheme it accepts and how to decompose it into bucket and object name. `GcsBlobStore` owns every bit of `gs://` parsing. Nothing else in the framework touches it.

2. **Null rejection.** A caller passing `null` as a URI is a programming error, not a runtime condition. The adapter enforces that upfront. In Java, `Objects.requireNonNull(uri, "uri must not be null")` (`GcsBlobStore.java:222`) throws `NullPointerException` with a useful message before anything touches the GCS client. In Python, `_parse` opens with an explicit `if uri is None: raise TypeError(...)` (`blob_store.py:89-90`). The error type differs by language — NPE in Java, `TypeError` in Python — because that is what each language's conventions demand, and the contract says nothing about error types. Adapters speak the language of their ecosystem.

3. **404 → contract semantics.** The `BlobStore` contract documents that `get` should raise `FileNotFoundException` for a missing object. GCS does not raise `FileNotFoundException`; it returns a null `Blob` from `Storage#get`. The adapter bridges that gap (`GcsBlobStore.java:84-90`): check for null, wrap in `UncheckedIOException` with `FileNotFoundException` as the cause. The caller gets the contract's promised exception, not GCS's null.

These decisions are not exotic. They are the mundane, necessary work that every real adapter has to do. The point of naming them is that they need to live somewhere, and if they live in the adapter, they are in exactly one place and that place has a contract to test against.

## GcsBlobStore — object storage with a URI parser inside

\index{GcsBlobStore|textbf}

`GcsBlobStore` implements `BlobStore` against the `com.google.cloud.storage.Storage` client. Its source lives at:

```
data-pipeline-libraries-java/data-pipeline-gcp-gcs-java/src/main/java/
    com/enrichmeai/culvert/gcp/gcs/GcsBlobStore.java
```

The class signature is straightforward:

```java
public final class GcsBlobStore implements BlobStore, AutoCloseable {

    public static final String SCHEME = "gs://";

    private final Storage client;

    // No-arg constructor for ServiceLoader discovery.
    public GcsBlobStore() {
        this(StorageOptions.getDefaultInstance().getService());
    }

    // Constructor for tests and custom-credential wiring.
    public GcsBlobStore(Storage client) {
        this.client = Objects.requireNonNull(client, "client must not be null");
    }
```

(Source: `GcsBlobStore.java:49-78`)

The no-arg constructor is the `ServiceLoader` entry point. GCS URIs carry the
bucket inline — `gs://my-bucket/path/to/file` — so no default bucket or
project ID is needed at construction time. Application Default Credentials
handle authentication. The injectable-client constructor exists for tests:
you pass a Mockito mock and never touch real GCS.

The `AutoCloseable` implementation is honest about the SDK's checked
exception:

```java
@Override
public void close() {
    try {
        client.close();
    } catch (Exception e) {
        if (e instanceof IOException ioe) {
            throw new UncheckedIOException(ioe);
        }
        throw new RuntimeException(e);
    }
}
```

(Source: `GcsBlobStore.java:193-204`)

`Storage#close` throws `Exception`, which is the kind of signature that makes
Java programmers wince. We narrow it: `IOException` becomes
`UncheckedIOException`; anything else becomes `RuntimeException`. Callers of
`close()` are not expected to handle storage-close failures; surfacing them as
unchecked is the pragmatic choice.

### URI parsing

The URI parser is a private static helper that gets everything else right
regardless of what the caller passes:

```java
private static ParsedUri parseUri(String uri) {
    Objects.requireNonNull(uri, "uri must not be null");
    if (!uri.startsWith(SCHEME)) {
        throw new IllegalArgumentException(
                "URI must start with " + SCHEME + ": " + uri);
    }
    String rest = uri.substring(SCHEME.length());
    int slash = rest.indexOf('/');
    String bucket;
    String objectName;
    if (slash < 0) {
        bucket = rest;
        objectName = "";
    } else {
        bucket = rest.substring(0, slash);
        objectName = rest.substring(slash + 1);
    }
    if (bucket.isEmpty()) {
        throw new IllegalArgumentException(
                "URI must include a bucket: " + uri);
    }
    return new ParsedUri(bucket, objectName);
}
```

(Source: `GcsBlobStore.java:221-243`)

Three cases are rejected immediately: `null` (NPE), non-`gs://` scheme
(`IllegalArgumentException`), and a missing bucket (`IllegalArgumentException`).
A URI with a bucket but no object name — `gs://my-bucket` — is valid only for
`list(prefix)`, which calls `parseUri` without the further check that a
non-empty `objectName` is present (`GcsBlobStore.java:212-218`). Every other
operation calls the stricter `parse(uri)` wrapper which asserts the object
name is non-empty.

The equivalent in Python is via `urllib.parse.urlparse` with the same three
guards (`blob_store.py:88-101`). There the non-`gs://` scheme raises
`ValueError` rather than `IllegalArgumentException` — same conceptual error,
idiomatic for each language.

### The core operations

\index{BlobStore!get}\index{BlobStore!put}\index{BlobStore!list}

`get`, `put`, `openInput`, `openOutput`, `list`, `exists`, `delete`, and `copy`
are all present, which is the full `BlobStore` surface. A few are worth a
closer look.

**`list`** returns an `Iterator<String>` rather than loading all object names
into memory. The implementation wraps GCS's `Page<Blob>` in a bespoke
iterator that reconstructs the full `gs://bucket/object` URI from the `Blob`'s
name field (`GcsBlobStore.java:123-144`). This is intentional: the contract
says to return absolute URIs, and the caller should not need to know the
bucket name separately.

**`delete`** is idempotent by contract. The GCS SDK's `Storage#delete` returns
`false` for a missing object rather than throwing, but a `StorageException`
with code 404 can still escape if the client is configured differently.
The adapter catches it explicitly (`GcsBlobStore.java:160-167`) and treats it
as a no-op, consistent with the contract's documented behaviour.

**`copy`** documents cross-store copies as out of scope:

```java
@Override
public void copy(String src, String dst) {
    if (!isGcsUri(src) || !isGcsUri(dst)) {
        throw new UnsupportedOperationException(
                "GcsBlobStore.copy only supports gs:// to gs:// copies; got "
                        + "src=" + src + ", dst=" + dst);
    }
    // ...
}
```

(Source: `GcsBlobStore.java:172-179`)

The contract's comment on `copy` (`BlobStore.java:60-63`) explicitly permits
this: "Cross-store copies are out of scope; implementations may throw
`UnsupportedOperationException` for foreign schemes." The adapter enforces
the boundary at the right place — before the URI parser gets a chance to
produce a confusing `IllegalArgumentException` about the scheme.

### Python parity

The Python adapter (`data-pipeline-libraries/data-pipeline-gcp-gcs/src/data_pipeline_gcp_gcs/blob_store.py`) mirrors the Java surface with one difference worth noting: the constructor takes an explicit `client` argument with no default (`blob_store.py:26-29`). There is no equivalent of the no-arg ServiceLoader constructor in Python — the adapter is wired up by autoconfig rather than by Java's ServiceLoader mechanism. That difference is a natural consequence of the two runtimes' different discovery models, and Chapter 15 covers autoconfig in detail.

The Python `_is_not_found` helper (`blob_store.py:103-108`) uses duck-typing
to check for 404 errors rather than importing `google.api_core.exceptions.NotFound`
directly. That keeps the adapter loosely coupled to the SDK version — a small
thing that has quietly saved us from a version bump once already.

## PubSubSource and PubSubSink — messaging with delivery decisions

\index{PubSubSource|textbf}\index{PubSubSink|textbf}

The messaging pair lives at:

```
data-pipeline-libraries-java/data-pipeline-gcp-pubsub-java/src/main/java/
    com/enrichmeai/culvert/gcp/pubsub/PubSubSource.java
    com/enrichmeai/culvert/gcp/pubsub/PubSubSink.java
```

with Python siblings at:

```
data-pipeline-libraries/data-pipeline-gcp-pubsub/src/data_pipeline_gcp_pubsub/io.py
```

The contracts they implement are `Source<T>` and `Sink<U>` from
`data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/`.
Both are `@FunctionalInterface` — `Source.read(RuntimeContext)` returns
`Iterator<T>`; `Sink.write(Iterator<U>, RuntimeContext)` consumes it
(`Source.java:20-30`, `Sink.java:16-26`).

The Pub/Sub SDK does not map cleanly onto those shapes. That is the whole
problem the adapters solve.

### PubSubSource — pulling and the at-most-once decision

\index{PubSubSource!at-most-once}

```java
public final class PubSubSource implements Source<PubsubMessage>, AutoCloseable {

    public static final int DEFAULT_MAX_MESSAGES = 100;

    private final SubscriberStub stub;
    private final String subscriptionName;
    private final int maxMessages;
```

(Source: `PubSubSource.java:50-57`)

The design is a synchronous pull wrapper. Each call to `read(context)` issues
one `pull` RPC against the subscription, acknowledges the batch eagerly, and
returns an iterator over the payloads. The delivery model is **at-most-once**:
a consumer that crashes mid-iteration after `read` has returned will lose the
pulled batch, because the acknowledgements were sent before the iterator was
handed back.

This is an explicit, documented decision, not an accident:

```java
// Eager ack: collect ackIds and acknowledge before exposing
// messages. This gives at-most-once semantics — documented on the
// class — and keeps the iterator simple (no per-message ack callback
// for the consumer to forget).
List<String> ackIds = new ArrayList<>(received.size());
List<PubsubMessage> payloads = new ArrayList<>(received.size());
for (ReceivedMessage rm : received) {
    ackIds.add(rm.getAckId());
    payloads.add(rm.getMessage());
}

AcknowledgeRequest ackRequest = AcknowledgeRequest.newBuilder()
        .setSubscription(subscriptionName)
        .addAllAckIds(ackIds)
        .build();
stub.acknowledgeCallable().call(ackRequest);

return payloads.iterator();
```

(Source: `PubSubSource.java:122-139`)

Why at-most-once? Because the `Source<T>` contract has no per-message ack
callback. There is nowhere to surface it. If we had tried to implement
at-least-once semantics through the `Source` interface alone, we would have
had to either (a) add a callback to the contract — which would break every
other `Source` implementation — or (b) require callers to cast to
`PubSubSource` and call a separate ack method, which defeats the purpose of
the abstraction. At-most-once with eager ack is the honest choice given the
contract shape.

The Javadoc is explicit: callers needing at-least-once semantics should wire
a separate `Subscriber`-based reader, not use this adapter
(`PubSubSource.java:24-28`).

The Python counterpart in `io.py` has slightly different timing. The Python
`read(context)` is a generator — it `yield`s each message as it processes the
received list and sends the `acknowledge` call after the loop finishes
(`io.py:37-62`). The ack goes out after all messages have been yielded, which
means a consumer that breaks out of the iteration early will still get the
whole batch acknowledged on the next garbage-collection cycle of the generator.
In practice this is a minor distinction — the Python code even labels it
"eager-ack" in its comment — but if you are writing contract tests, the
difference in timing is real.

**`subscriptionName`** must be the fully-qualified resource name:
`projects/{project}/subscriptions/{name}`. The constructor does not validate
this format — it trusts the caller has used
`ProjectSubscriptionName.of(project, name)` — but an unqualified name will
produce a Pub/Sub gRPC error at pull time that will not be pleasant to
diagnose. A note for the future.

`PubSubSource` implements `AutoCloseable` because `SubscriberStub` extends
`BackgroundResource`, which itself extends `AutoCloseable`
(`PubSubSource.java:154-156`). Use it in a try-with-resources and the gRPC
channel closes cleanly.

### PubSubSink — publish futures and surface-level failures

\index{PubSubSink!PubSubPublishException}

`PubSubSink` wraps a `Publisher` — the Pub/Sub SDK's async publish client.
The mismatch with the `Sink` contract is stark: `Sink.write` is synchronous
from the caller's perspective; `Publisher#publish` returns an `ApiFuture<String>`
immediately. The adapter bridges them by collecting all futures and then
blocking:

```java
@Override
public void write(Iterator<PubsubMessage> records, RuntimeContext context) {
    Objects.requireNonNull(records, "records must not be null");

    List<ApiFuture<String>> futures = new ArrayList<>();
    while (records.hasNext()) {
        PubsubMessage message = records.next();
        if (message == null) {
            throw new NullPointerException(
                    "records iterator yielded a null PubsubMessage");
        }
        futures.add(publisher.publish(message));
    }

    if (futures.isEmpty()) {
        return;
    }

    try {
        ApiFutures.allAsList(futures).get();
    } catch (InterruptedException e) {
        Thread.currentThread().interrupt();
        throw new PubSubPublishException(
                "Interrupted while waiting for Pub/Sub publish futures", e);
    } catch (ExecutionException e) {
        throw new PubSubPublishException(
                "Pub/Sub publish failed: " + e.getCause().getMessage(),
                e.getCause());
    }
}
```

(Source: `PubSubSink.java:79-109`)

The `ApiFutures.allAsList(futures).get()` call resolves when every future
resolves; if any fails, the composite future fails with the first cause.
That cause surfaces as `PubSubPublishException` — a public `RuntimeException`
subclass nested in `PubSubSink` (`PubSubSink.java:139-145`). The wrapper
exists so callers can catch publish failures specifically without depending
on the GCP SDK's exception hierarchy at the catch site.

One nuance the Javadoc is careful about: later records in the same batch may
have already been published before the first failure surfaces
(`PubSubSink.java:68-71`). This is partial-failure territory, and there is no
clean way to make it otherwise when the underlying transport is asynchronous
and batch-acknowledged. The honest answer is that `PubSubSink` gives you
synchronous error surfacing, not idempotent batch retry. If you need the
latter, you need a richer layer on top.

**Lifecycle asymmetry.** `Publisher` does not implement `AutoCloseable`. It
exposes `shutdown()` + `awaitTermination(long, TimeUnit)` instead, which is
an older Java lifecycle convention. Per the framework's rule — "AutoCloseable
only when the wrapped client supports it" — `PubSubSink` also does not
implement `AutoCloseable`. There is an explicit `shutdown` method
(`PubSubSink.java:124-127`) that passes through to the publisher. Wire it
into your pipeline teardown hook; the framework does not call it
automatically.

This is the direct contrast to `GcsBlobStore` (which does implement
`AutoCloseable` because `Storage#close` exists) and `PubSubSource` (which
does, because `SubscriberStub` extends `BackgroundResource`). Three adapters,
two different lifecycle shapes — the inconsistency is GCP's, not ours.

The Python `PubSubSink` (`io.py:65-93`) takes a similar approach: collect
futures from `publisher.publish(topic_path, data, **attributes)` and block on
each with `future.result()` (`io.py:91-93`). The Python publisher's topic path
is passed per-call rather than being baked into the publisher object, which is
why `PubSubSink.__init__` accepts both `publisher` and `topic_path` separately.

### What the contract hides — and what it doesn't

These two adapters between them implement four contract methods: `BlobStore` (8
methods), `Source.read` (1), `Sink.write` (1). The pipeline logic that uses
them sees `BlobStore`, `Source<PubsubMessage>`, and `Sink<PubsubMessage>`. It
does not see `Storage`, `SubscriberStub`, `Publisher`, `ApiFuture`, or any
GCS-specific URI handling.

What the contract does *not* hide is the message type. `PubSubSource` and
`PubSubSink` are both typed over `PubsubMessage` — a Pub/Sub SDK protobuf type.
That means pipeline logic that uses these adapters has a dependency on the
Pub/Sub SDK even if it never touches a `Publisher`. We considered a
message-type abstraction (`Map<String, Object>` or a bespoke record) but
rejected it: the serialisation logic would live somewhere, and pushing it into
an intermediate type made the adapter more complex without removing the SDK
dependency in any useful sense. The Python adapters do use
`Mapping[str, Any]` (`io.py:12`) — a more natural choice in Python where
protobuf types are less pervasive — so the two sides have drifted on message
representation. Chapter 6 covers polyglot parity in more detail; the honest
summary is that this is the seam that needs a contract-test to keep it honest.

## The contract-test anchor

Both adapters are tested against contract mixins from `data-pipeline-contract-tests`.
The Python GCS test binds `BlobStoreContract` to `GcsBlobStore` via
`TestGcsBlobStoreContract(BlobStoreContract)` with a mocked `storage.Client`
(`tests/test_blob_store.py:22-24`). The contract mixin exercises every method
in the `BlobStore` surface — not just the happy path — with the same fixture
setup. That is the mechanism that keeps the adapter honest: you cannot add an
operation to the contract without updating the mixin, and you cannot implement
a broken adapter without the mixin catching it.

Chapter 16 goes into contract testing in depth. For now, the key point is
that "implements BlobStore" is not a claim you verify by inspection. It is a
claim you verify by binding the implementation to the contract-test suite and
running it.

## FinOps trackers — a forward note

\index{GcsCostTracker}\index{PubSubCostTracker}

Alongside the adapters sit two cost-tracking classes: `GcsCostTracker`
(`GcsBlobStore.java`'s sibling) and `PubSubCostTracker`. They record bytes
written, bytes stored, and message-throughput costs against a `FinOpsSink` —
the framework's contract for cost attribution. They are baked into the
adapter modules so you get cost visibility as part of the storage and messaging
wiring, not as an afterthought.

Chapter 13 covers the FinOps layer properly. The short version: per-GiB
storage cost for GCS (`GcsCostTracker.java:90`); per-TiB throughput cost for
Pub/Sub (`PubSubCostTracker.java:81`); both emit `CostMetrics` records via
`FinOpsSink` keyed to a `run_id` so you can join them to the audit trail.

## What we learnt

I will confess that writing these adapters was more work than I expected,
and most of that work was *not* the GCS or Pub/Sub API calls. Those are
well-documented. What took time was the small decisions: null handling that
speaks each language's idiom, URI validation that belongs in the adapter
rather than the contract, lifecycle shapes that differ between adapters because
the underlying SDKs differ. None of it is glamorous. All of it matters when
you are debugging a pipeline at two in the morning.

The reward is that `BlobStore`, `Source`, and `Sink` are now GCP-concrete
without either being GCP-aware. The next chapter (Chapter 8) takes a similar
approach to BigQuery — the warehouse adapter — which has more surface area and
a few sharper edges.

\begin{takeaways}
\textbf{Key takeaways}
\begin{itemize}
  \item \textbf{The contract declares URIs opaque; the adapter owns the scheme.}
        \texttt{BlobStore} says nothing about \texttt{gs://}. \texttt{GcsBlobStore}
        owns every byte of URI parsing, null-rejection (NPE in Java,
        \texttt{TypeError} in Python), and scheme validation
        (\texttt{IllegalArgumentException} / \texttt{ValueError}).
        Different error types per language are deliberate — adapters speak
        their ecosystem's idiom.
  \item \textbf{Eager-ack is an explicit delivery model, not an oversight.}
        \texttt{PubSubSource} acknowledges the pulled batch before returning
        the iterator — at-most-once semantics by design. The
        \texttt{Source<T>} contract has no per-message ack callback; any
        attempt to wire at-least-once semantics through the same interface
        would break every other \texttt{Source} implementation.
  \item \textbf{Publish futures block synchronously; failures surface as
        \texttt{PubSubPublishException}.} The sink collects all futures from
        a \texttt{write} call and waits for them before returning. Silent
        publish failures are not acceptable; the exception type is public so
        callers can catch it without depending on the GCP SDK's hierarchy.
  \item \textbf{Lifecycle shapes are inherited from the SDK, not invented.}
        \texttt{GcsBlobStore} and \texttt{PubSubSource} implement
        \texttt{AutoCloseable} because their wrapped clients support
        \texttt{close()}. \texttt{PubSubSink} does not, because
        \texttt{Publisher} uses \texttt{shutdown}/\texttt{awaitTermination}.
        The asymmetry is GCP's; the adapters document it honestly.
  \item \textbf{Contract tests are the verification mechanism.} Claiming an
        adapter "implements \texttt{BlobStore}" means nothing until the
        implementation is bound to the \texttt{BlobStoreContract} test mixin.
        The mixin is the executable specification.
\end{itemize}
\end{takeaways}

\newpage

# Chapter 8 — Warehouse and Job Control

## The double life of a columnar store

In Chapter 5 I walked through the six methods on the `Warehouse` contract — the tabular complement to `BlobStore`, the thing that can run a SELECT, fire a bulk load, and clone a table server-side. I made a small drama out of having forgotten `copy` entirely when writing from memory, and used it to argue that the contract is the memory you cannot argue with.

What I did not explain in Chapter 5 is the thing that most surprises engineers seeing Culvert's GCP adapter stack for the first time: BigQuery is not just the warehouse. It is also the pipeline-job ledger. Every `createJob`, every `updateStatus`, every `markFailed` — those are `UPDATE … WHERE run_id = @run_id` statements issued against BigQuery DML, not against a Postgres primary store or a Cloud Spanner transaction. The same columnar OLAP store that scans terabytes in seconds is doing your row-by-row job bookkeeping.

This is a deliberate choice, and it is worth explaining properly, because it is not the choice I would have made in 2019. My instinct — I suspect yours too — is to reach for a transactional database for state management. PostgreSQL for the job ledger, BigQuery for the warehouse. That is two data stores, two IAM surfaces, two connection pools, two billing lines, and a new class of cross-store consistency bug to write integration tests for. When I worked out that BigQuery DML was fast enough at pipeline-job volumes — and that having the job history SQL-joinable against the pipeline output tables was genuinely useful for debugging — I kept it. This chapter explains how that works, what it costs you, and where the seam is.

## BigQueryWarehouse: five of six, honestly

The contract surface from Chapter 5:

```
query(sql, params)       → Iterator<Map<String, Object>>
execute(sql, params)     → void
loadFromUri(uri, table, schema) → long
merge(sourceTable, targetTable, keys) → long
copy(sourceTable, targetTable) → long
tableExists(fqtn)        → boolean
```

`BigQueryWarehouse` implements five of those. The sixth — `merge` — throws `UnsupportedOperationException`. The Javadoc is honest about why:

```java
// BigQuery's MERGE syntax requires explicit non-key column lists in
// `WHEN MATCHED THEN UPDATE SET ...`; `SET t.* = s.*` is not valid.
// Generating the column list requires a schema lookup against the
// source table, which expands this method's responsibility beyond
// sprint-1's "match the pilot's adaptation patterns" rule.
throw new UnsupportedOperationException(
        "merge() is sprint-4 scope (requires column-aware SQL generation). "
                + "Use execute(String, Map) with an explicit MERGE statement until then. "
                + "Tracked at https://github.com/enrichmeai/gcp-pipeline-reference/issues/6");
```
[`data-pipeline-libraries-java/data-pipeline-gcp-bigquery-java/src/main/java/com/enrichmeai/culvert/gcp/bigquery/BigQueryWarehouse.java:164`]

I want to be plain about this because the task sheet I handed the team for Chapter 8 listed all six methods as if they work. They do not all work. BigQuery's MERGE requires you to enumerate every column you want updated; generating that list requires a prior schema fetch, and that turned the implementation into a more complicated beast than a Sprint 1 deliverable should be. The workaround — pass an explicit MERGE statement through `execute()` — is not elegant, but it is honest. The issue is tracked; it will land.

The five that do work follow a consistent pattern: every operation goes through a BigQuery `Job`. `query` and `execute` use `QueryJobConfiguration`; `loadFromUri` uses `LoadJobConfiguration`; `copy` uses `CopyJobConfiguration`. The client blocks on `job.waitFor()` and the result is unpacked in a single private helper, `waitFor()`, which distinguishes the three error modes — null job (quota/ADC failure), job disappeared before completion (`NoSuchElementException`), job completed with a status error (`BigQueryException` synthesised from the job's error message) — at [`BigQueryWarehouse.java:360`].

The one design decision worth calling out is in `query`. Rather than materialising the entire `TableResult` into a `List`, the adapter wraps `result.iterateAll().iterator()` in an anonymous `Iterator<Map<String, Object>>` that pages through BigQuery's cursor lazily. The contract's Javadoc requires this: *"implementations should not buffer the entire result in memory."* A 50-million-row query result should not allocate a 50-million-entry list at [`BigQueryWarehouse.java:249`].

`loadFromUri` does the one thing that makes BigQuery an attractive warehouse: it lets you hand it a `gs://` URI and it arranges the bulk load server-side. The adapter guesses the format from the URI extension — CSV, Parquet, Avro, ORC, or newline-delimited JSON as fallback — at [`BigQueryWarehouse.java:341`]. GCS-to-BigQuery at that point is a metadata operation on Google's infrastructure; the data does not traverse your network. `copy` is even cheaper: it is a BigQuery `CopyJob`, which is a metadata-only table clone. The output row count is retrieved from `table.getNumRows()` after the copy, not from any job statistics, because `CopyStatistics` does not expose a row count.

## The fqtn convention

`BigQueryWarehouse` and `BigQueryJobControlRepository` both parse table names the same way. The adapter accepts either two-part `dataset.table` or three-part `project.dataset.table`. Two-part names default to the warehouse's configured `projectId`. The parsing lives in `parseFqtn()` at [`BigQueryWarehouse.java:287`] and is replicated as template-literal construction in `BigQueryJobControlRepository` at [`BigQueryJobControlRepository.java:73`]:

```java
this.fqtn = "`" + projectId + "." + dataset + "." + table + "`";
```

The backtick-quoting matters. BigQuery's SQL parser requires backtick-quoted fully-qualified table names in parameterised DML statements. Miss the backticks and you get a parse error; this is one of those things you learn by getting the error and then reading the error message for longer than you should need to.

## BigQueryJobControlRepository: the ledger

The job-control contract — `JobControlRepository` — is the pipeline state machine. Eleven methods: create a job row, fetch it, transition its status, mark it failed, mark it retrying, list pending runs, report per-entity status, list failed jobs, query FDP model status, clean up a partial load, and attach cost metrics. The Java surface at [`data-pipeline-libraries-java/data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/JobControlRepository.java:25`] is a one-for-one mirror of the Python job-control repository documented in the Python `gcp_pipeline_core.job_control.repository` module — the Java port carries that lineage explicitly in its Javadoc at line 28.

`BigQueryJobControlRepository` implements all eleven. Every method issues a parameterised BigQuery query. The parameters are bound using `QueryParameterValue` typed constructors — `.string()`, `.int64()`, `.float64()`, `.date()`, `.timestamp()` — rather than string interpolation. That is not a minor style point. BigQuery parameterised queries prevent SQL injection and, more practically in a pipeline context, prevent the kind of run-ID collision where an accidental quote in a system identifier corrupts the WHERE clause.

The `updateStatus` method illustrates the pattern. Status transitions branch on three cases:

```java
if (status == JobStatus.RUNNING) {
    // stamps started_at
} else if (status == JobStatus.SUCCEEDED) {
    // stamps completed_at + record_count
} else {
    // bumps status + updated_at only
}
```
[`BigQueryJobControlRepository.java:159`]

This branching comes directly from the Python original. RUNNING starts a job's clock; SUCCEEDED closes it and records the final row count; every other transition (FAILED, RETRYING, CANCELLED) only updates status and the audit timestamp. The split is pragmatic: it avoids nulling out `started_at` or `completed_at` on intermediate transitions, which would make duration queries on the `pipeline_jobs` table unreliable.

`markFailed` is the one that matters most at three in the morning. It writes structured error context — `error_code`, `error_message`, `failure_stage`, and an optional `error_file_path` (a `gs://` URI pointing at the quarantined records that caused the failure) — atomically with the status flip. The framework does not require you to write these separately and hope the process does not crash between statements. They go in one UPDATE at [`BigQueryJobControlRepository.java:197`].

`cleanupPartialLoad` is the twin of `markFailed` for recovery. Pipeline-written target tables carry a `_run_id STRING` column populated at load time. When a run fails and the caller wants to retry cleanly, `cleanupPartialLoad` issues `DELETE FROM <table> WHERE _run_id = @run_id` to remove any partially-written rows before the orchestrator resubmits. The `RetryOrchestrator` helper at [`BigQueryRetryOrchestrator.java`] sequences the full lifecycle: detect prior partial load, clean it, mark retrying, return cleared state. The idempotency guarantee is explicit: if the job is already in `RETRYING` state, the orchestrator does not call `markRetrying` again, which prevents double-incrementing the retry counter when a caller restarts an already-in-progress re-run.

## The honest trade-off

Using BigQuery as a CRUD store has real costs. BigQuery DML — UPDATE, DELETE — is not free. Each statement competes for DML slots and can take seconds to complete at low concurrency. At pipeline-job volumes — dozens of jobs per hour, not tens of thousands per second — the latency is acceptable. At application-CRUD volumes it would be absurd.

The benefit is that the job history is a BigQuery table, full stop. You can join it against your pipeline output tables, your cost metrics, your audit events, your BI exports. Debugging a failed run means one SQL query against a familiar interface, not a context switch to a different database with a different auth model and a different query tool. The operations team we work with found that more valuable than I expected.

The other thing you give up is transactional isolation. BigQuery DML does not support BEGIN/COMMIT in the sense that PostgreSQL does. Two concurrent `markFailed` calls for the same `run_id` are theoretically possible — BigQuery will serialise them, but the result is non-deterministic ordering. In practice, a well-structured pipeline runner ensures that only one process owns a given `run_id` at any moment. The contract documentation at [`JobControlRepository.java:17`] is explicit: *"implementations are expected to be transactional within a single `runId`."* The BigQuery implementation honours the spirit of that clause by relying on single-writer discipline rather than database locks. If your runner does not enforce single-writer discipline, you will find out the hard way.

## BigQueryFinOpsSink: the cost trail

`FinOpsSink` is a functional interface with one method: `record(CostMetrics metrics, FinOpsTag tags)`. The tag carries attribution — system, environment, cost centre, owner, run ID. The metrics carry the numbers — bytes scanned, bytes written, bytes stored, slot-milliseconds, compute units, estimated cost in USD. The sink writes them wherever the team aggregates them. On GCP, that is BigQuery.

`BigQueryFinOpsSink` implements `record` via a streaming insert: `client.insertAll(InsertAllRequest)` at [`BigQueryFinOpsSink.java:100`]. One call per cost-incurring operation. The Javadoc is candid about the trade-off: streaming inserts land in BigQuery's streaming buffer, queryable within seconds but not immediately visible to `COPY` or `EXPORT` jobs; the buffer flushes to managed storage on BigQuery's own schedule, typically within 90 minutes. Streaming inserts also cost money — per GB written to the buffer on top of regular storage. For high-volume cost emission, a load-job-based variant would be cheaper; that is flagged in the Javadoc at [`BigQueryFinOpsSink.java:30`] as a future-sprint item.

The partial-failure handling is worth noting: `InsertAllResponse.hasErrors()` is checked explicitly at line 101, and any per-row error throws `FinOpsInsertException` rather than silently swallowing it. Silently dropping cost rows would undermine the FinOps audit trail. The exception preserves the full GCP `Map<Long, List<BigQueryError>>` so a caller can report which rows failed and why.

The map fields — `CostMetrics.labels()` and `FinOpsTag.extra()` — are flattened into `RECORD<key STRING, value STRING>` arrays via `flattenMap()` at [`BigQueryFinOpsSink.java:149`]. BigQuery's stable way to ship arbitrary key-value data without a DDL change per new label. The query side UNNESTs the array; `CostAnalysisQueries` at [`BigQueryCostTracker:java`] ships the canned SQL for the common aggregations.

## BigQueryCostTracker: the formula

`BigQueryCostTracker` sits one level above `BigQueryFinOpsSink`. It reads a completed `Job`'s statistics and builds the `CostMetrics` record before handing it to the sink. The pricing model is:

```java
public static final long BYTES_PER_TIB = 1_099_511_627_776L; // 2^40
public static final double QUERY_COST_USD_PER_TIB = 5.00;
public static final double LOAD_COST_USD_PER_TIB = 0.01;
```
[`BigQueryCostTracker.java:81`, `90`, `103`]

The formula that applies those constants:

```java
private static double bytesToUsd(long bytes, double costPerTib) {
    if (bytes <= 0L) {
        return 0.0;
    }
    return (double) bytes / (double) BYTES_PER_TIB * costPerTib;
}
```
[`BigQueryCostTracker.java:321`]

Called for query jobs at line 243: `double costUsd = bytesToUsd(bytesScanned, QUERY_COST_USD_PER_TIB)`. Note the binary definition of TiB — 2^40 bytes, not 10^12. BigQuery's on-demand pricing uses the binary definition. Using 10^12 instead would undercount the estimated cost by about 9.95%. That is not a rounding error; it is an invoice surprise. The comment on the constant says as much.

`LOAD_COST_USD_PER_TIB = 0.01` has an honest footnote: BigQuery batch loads are actually free to ingest. The `$0.01` rate is a GCS-egress-equivalent accounting placeholder — the cost of moving data into BigQuery falls on the GCS side, not the BigQuery load side. Teams that do not pay GCS egress fees for this path may legitimately set it to zero. It is here to give the cost trail a non-null entry for load operations; otherwise load jobs appear free in the attribution dashboard and the FinOps team gets confused about why ingestion looks so cheap.

The dry-run pre-flight — `estimateDryRun()` at line 193 — is a useful capability with a documented uncertainty. BigQuery dry-run jobs populate `getTotalBytesBilled()` on *some* configurations; on others they populate only `getTotalBytesProcessed()`. The method tries `billed` first, falls back to `processed` if billed is null or zero, emits a `WARN`, and ultimately returns a zero estimate if both are absent. The Javadoc at line 54 flags this as a runtime guarantee risk and notes that the emulator integration test (`BigQueryCostTrackerIT`) is the place to verify the behaviour before trusting it in production. That is the kind of honesty I want baked into the implementation, not added later as a postmortem note.

## Why one store

I will make the argument plainly, because the alternative — BigQuery for the warehouse, a separate transactional store for the ledger — is the one I get asked about most often.

The separate-store approach is perfectly defensible. A Cloud Spanner instance or a Cloud SQL PostgreSQL gives you proper serialisable isolation, sub-millisecond commit latency, and a familiar JDBC driver. You know exactly what you are getting.

What it also gives you is a second IAM surface, a second connection pool, a second backup policy, a second point of failure, and a billing line that will confuse whoever does the next cost review. It means that debugging a failed run requires querying two databases and mentally joining the results. It means that your FinOps dashboard cannot JOIN the job ledger against the cost metrics table, because they live in different systems.

BigQuery-as-ledger trades transactional isolation guarantees for operational simplicity. At pipeline-job frequencies — where "high volume" means tens of jobs per minute — the DML latency is negligible and the joining capability is immediately useful. If you are building something where hundreds of processes are competing to update the same job row simultaneously, this is not the right design. For the data pipelines this framework targets, it has been the right design.

\begin{takeaways}
\textbf{Key takeaways}
\begin{itemize}
  \item \texttt{BigQueryWarehouse} implements five of the six \texttt{Warehouse} contract methods. \texttt{merge()} throws \texttt{UnsupportedOperationException} — BigQuery requires explicit column enumeration in MERGE that the sprint-1 implementation defers; callers pass explicit MERGE SQL via \texttt{execute()} until sprint-4 lands. [\texttt{BigQueryWarehouse.java:164}]
  \item Every operation goes through a BigQuery \textit{Job} — \texttt{QueryJobConfiguration} for query/execute, \texttt{LoadJobConfiguration} for bulk load, \texttt{CopyJobConfiguration} for table clone. The \texttt{waitFor} helper distinguishes null job, vanished job, and error-status job in one place. [\texttt{BigQueryWarehouse.java:360}]
  \item Using BigQuery as the job ledger is a deliberate trade: one IAM surface, one billing line, joinable job history against pipeline output tables — at the cost of DML latency and no serialisable isolation. Acceptable at pipeline-job frequencies; not at OLTP frequencies.
  \item The query cost formula is \texttt{bytes / BYTES\_PER\_TIB * QUERY\_COST\_USD\_PER\_TIB} where \texttt{BYTES\_PER\_TIB = 1\_099\_511\_627\_776L} (2\textsuperscript{40}, the binary definition). Using the decimal 10\textsuperscript{12} would undercount by roughly 10\%. [\texttt{BigQueryCostTracker.java:81}, \texttt{90}, \texttt{321}]
  \item \texttt{BigQueryFinOpsSink} uses streaming inserts — rows are queryable within seconds but not immediately available to COPY/EXPORT jobs; the streaming buffer flushes on BigQuery's schedule, typically within 90 minutes. Streaming inserts also carry a per-GB cost. [\texttt{BigQueryFinOpsSink.java:30}]
  \item Python job-control parity already exists in the predecessor \texttt{gcp\_pipeline\_core.job\_control.repository}. A Python \texttt{Warehouse} adapter for BigQuery is in progress on a separate branch; it is not yet shipped.
\end{itemize}
\end{takeaways}

\newpage

# Chapter 9 — Execution: Beam on Dataflow

The last chapter drew the map. Java owns execution; Python owns orchestration,
transforms, and the dbt layer. That division is not a preference — it is a
decision taken empirically, under load, with a real bill arriving every month.
This chapter is the proof of the Java side of that map: why execution became
Java's lane, how the Culvert contracts cross the boundary into Apache Beam, and
what the two classes at the heart of `data-pipeline-gcp-dataflow-java` actually
do.

The worked example throughout is the problem that forced the decision: mainframe
ingestion, HDR/TRL files, and the question of whether Python could keep up.

## Why execution is Java's lane

Apache Beam is not a fashionable technology in 2026. The Spark crowd thinks it
is over-engineered. The DuckDB crowd thinks any distributed engine is overkill.
The Snowflake crowd thinks ingestion is something you buy, not build. And yet,
for a particular shape of problem — high-volume, schema-validated, batch-or-streaming,
on Google Cloud — Beam on Dataflow is still the right answer.

The shape is roughly this: you have files on the order of gigabytes-to-terabytes,
you need per-record transformations that do not parallelise well in pure SQL, you
need side outputs for error quarantine, and you want managed autoscaling. Dataflow
gives you all of that in exchange for one Docker image and a JSON parameter file.

The throughput gap between the Java and Python SDKs is real. Java Beam delivers
roughly 2–3× more processed records per Dataflow dollar than Python Beam, and
the reason is not that Python is a slow language in general — it is two specific
things. First, Dataflow Runner v2 (the mode Python pipelines always use) routes
work through an SDK harness container that sits alongside the worker JVM. Every
record crosses that harness-to-worker boundary; the JVM does not have an
equivalent hop. Second, on the hot path, Java serialises through Kryo or AvroIO,
both of which are extremely fast; Python serialises through CPython's pickle
machinery, which is not.

For a pipeline doing heavy per-record work — parsing, enrichment, ML inference —
the CPU time on the actual business logic swamps the serialisation cost and the
SDK matters less. But mainframe ingestion is *not* that kind of pipeline. The
records are wide, the per-record logic is simple, and serialisation sits right
in the critical path.

Volume is what makes the trade-off worth having the conversation about. Below
roughly 50 million rows per day, the overhead of running a polyglot toolchain is
a far bigger cost than the compute bill. Above roughly 500 million rows per day —
which is perfectly normal for a corporate-bank card-transaction or call-detail
feed — a single high-throughput entity can cost you £8–12K per month on Python
Beam where the Java equivalent would run at £3–5K per month. At that point the
saving is real money, it recurs every month, and it is worth the polyglot tax.

The cultural dimension matters too, and it is underrated. Mainframe operations
teams are overwhelmingly Java-oriented. If you are writing files the mainframe
will consume — segment-transform write-back, batch settlement feeds, regulatory
exports — Java has the richer ecosystem: `com.legstar.*` for COBOL copybook\index{COBOL copybook}
binding, `Cp037` and `Cp1047` EBCDIC\index{EBCDIC} support via the standard JDK, IBM's own
JZOS toolkit for direct VSAM interaction. A Python receive-side pipeline feels
foreign to mainframe ops in a way that a Java one does not.

All of this is why — as Chapter 6's division-of-labour table records — the
Dataflow/execution row is: **Java (Beam).** The predecessor Python Beam path is
not being ported forward. `data-pipeline-gcp-dataflow-java` is the
lane, and it has no Python sibling.

## The HDR/TRL mainframe problem

Before we look at how Culvert solves the execution problem in Java, it is worth
understanding exactly what the execution problem is. The mainframe extract format
that drove everything is the HDR/TRL pattern.

A typical mainframe extract looks like this:

```
HDR|customers|20260417|0001|500000
0001|Alice Smith|1985-03-22|SW1A 1AA|2010-06-12T09:14:00Z
0002|Bob Jones |1979-11-04|EH8 9YL |2007-02-19T14:22:30Z
...
0500000|Zara Patel|1992-08-15|M1 1AA|2020-12-30T16:45:00Z
TRL|customers|20260417|0001|500000
```

The `HDR` row carries metadata: entity name, extract date, batch number, expected
record count. The `TRL` row repeats this metadata as a self-check. The body rows
are the actual data.

This pattern is older than I am, and it is everywhere. It is also subtly tricky
to handle in a distributed system, because Beam's parallel execution model assumes
records are independent, and HDR/TRL rows are not. The envelope must be separated
from the body; the expected count in the envelope must be checked against what
actually arrived; and this check must happen *after* all the body records have
been processed, which in a distributed job means after all the workers have
finished.

Real mainframes do not always send a 500,000-row file as one object either. They
sometimes split it into chunks:

```
customers.20260417.001of005.csv
customers.20260417.002of005.csv
...
customers.20260417.001of005.ok
```

Each chunk has its own HDR and TRL. Each `.ok` file signals that one chunk is
complete. You must wait for all chunks, reassemble them in order, and then treat
them as one logical extract. This kind of code is unglamorous and easy to get
wrong. It is also code that a bank runs every day at four in the morning, and
when it breaks, people notice.

The question was whether the Python Beam library we had built could handle this
at corporate-bank volume. The answer was: yes, but not cheaply. The arithmetic
eventually compelled us to the conclusion that execution needed to move to Java.
That conclusion is now the Culvert decision record: execution is Java's lane,
full stop.

The Java Culvert layer does not (yet) ship the rich library of HDR/TRL-specific
transforms that the old Python pipeline had — `HDRTRLParser`, `RobustCsvParseDoFn`,
`SchemaValidateRecordDoFn`, and the rest. Those belong to the predecessor project
and are not being ported. What Culvert ships is the execution *bridge*: the
mechanism by which any `PipelineStage` implementation can be run on Dataflow,
with full instrumentation, in a way that is completely invisible to the stage
itself. The stage author writes business logic against the contracts; the bridge
handles Beam.

## The contract: `Pipeline` and `PipelineStage`

The contracts involved in execution are small, by design. From
`data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/Pipeline.java`
(lines 1–30):

```java
public interface Pipeline {
    String name();
    List<PipelineStage> stages();
    void validate();
}
```

That is the whole interface. It is scheduler-agnostic: the pipeline describes a
DAG, and does not know or care whether that DAG will run on Dataflow, on a local
DirectRunner, on a future AWS Step Functions executor, or anything else. The
runtime picks it up and decides.

`PipelineStage`\index{PipelineStage} is equally spare
(`data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/PipelineStage.java`,
lines 1–31):

```java
public interface PipelineStage {
    String name();
    List<String> inputs();
    List<String> outputs();
    void execute(RuntimeContext context);
}
```

`inputs()` and `outputs()` are lists of logical names — strings — that the
framework uses to compute execution order and validate that every input has a
producer. `execute()` is `void` and side-effecting: the stage reads from sources
and writes to sinks through the adapters on the `RuntimeContext`. The stage does
not return a value, does not expose element counts, and does not know which runner
it is executing on.

This is also where the `Transform<V,W>` contract fits in — and where it
*currently does not*. `Transform`
(`data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/Transform.java`,
lines 17–27) is the element-level map contract:

```java
@FunctionalInterface
public interface Transform<V, W> {
    Iterator<W> apply(Iterator<V> records, RuntimeContext context);
}
```

An element-level Beam execution — where a stage maps an input `PCollection` to
an output `PCollection` so Beam can fuse and parallelise the data flow — would
require bridging `Transform<V,W>` into a proper `DoFn`. That is not what
`StageTransform` does today. Bridging `Transform<V,W>` at the element level is
explicitly deferred (StageTransform.java:35–39). The current bridge triggers
`execute()` once; element-level translation is sprint-future. It is important to
be precise about this distinction, because the architecture is built to
accommodate the upgrade path — but the upgrade has not been done yet.

## `DataflowPipeline`: the adapter

`DataflowPipeline`\index{DataflowPipeline} implements `Pipeline` and adds two
utilities on top of the base contract. The full source is in
`data-pipeline-gcp-dataflow-java/src/main/java/com/enrichmeai/culvert/gcp/dataflow/DataflowPipeline.java`.

Construction is strict and predictable (lines 72–83):

```java
public DataflowPipeline(String name, List<PipelineStage> stages) {
    Objects.requireNonNull(name, "name must not be null");
    Objects.requireNonNull(stages, "stages must not be null");
    if (name.isBlank()) {
        throw new IllegalArgumentException("name must not be blank");
    }
    if (stages.isEmpty()) {
        throw new IllegalArgumentException("stages must not be empty");
    }
    this.name = name;
    this.stages = List.copyOf(stages);
}
```

`List.copyOf` makes the stage list immutable immediately. Nothing downstream can
mutate the topology after construction. I like this pattern — it removes an entire
class of bugs where something hands you a pipeline and then quietly modifies the
stage list later.

### `validate()`: the graph checker

`validate()` (lines 103–150) enforces three properties before anything runs:

1. **Stage names are unique.** Two stages with the same name is a configuration
   error that would produce nonsensical topological ordering.
2. **Every input references an output with a producer.** If a stage declares that
   it consumes `"rows"` but no upstream stage produces `"rows"`, the graph is
   broken — no point launching Dataflow workers to discover that.
3. **No cycles.** Checked by DFS; the cycle detection path (lines 342–365) trims
   the visiting set to the cycle itself and surfaces the full path, which makes
   debugging a misconfigured graph much less painful.

`validate()` runs again inside `buildBeam()` before any Beam pipeline is
constructed. You cannot accidentally submit a malformed graph to Dataflow.

### `buildBeam()`: the translation

`buildBeam(PipelineOptions options, RuntimeContext context)` (lines 199–215) is
where the Culvert topology becomes a Beam pipeline:

```java
public org.apache.beam.sdk.Pipeline buildBeam(
        PipelineOptions options, RuntimeContext context) {
    Objects.requireNonNull(options, "options must not be null");
    Objects.requireNonNull(context, "context must not be null");
    validate();

    org.apache.beam.sdk.Pipeline beam =
            org.apache.beam.sdk.Pipeline.create(options);
    Map<String, PipelineStage> byName = new HashMap<>();
    for (PipelineStage stage : stages) {
        byName.put(stage.name(), stage);
    }
    for (String stageName : topologicalOrder()) {
        PipelineStage stage = Objects.requireNonNull(
                byName.get(stageName), () -> "no stage named " + stageName);
        beam.apply(StageTransform.of(stage, context));
    }
    return beam;
}
```

The key step is `topologicalOrder()` (lines 278–324), which runs Kahn's algorithm
over the input/output edge graph. This means the declaration order of stages in
the constructor is irrelevant — the execution order is derived from data
dependencies, not from the order you wrote them down. The test at
`DataflowPipelineExecutionTest.java:63–65` deliberately declares stages out of
dependency order to prove this:

```java
// Declare OUT of dependency order: "transform" depends on "read"'s
// output, but is declared first. buildBeam must topologically sort.
PipelineStage read = new RecordingStage("read", List.of(), List.of("rows"));
PipelineStage transform = new RecordingStage("transform", List.of("rows"), List.of("clean"));
DataflowPipeline pipeline =
        new DataflowPipeline("two-stage", List.of(transform, read));
```

`topologicalOrder()` returns `["read", "transform"]` regardless of declaration
order. Applied to the HDR/TRL problem: a real ingestion pipeline would have a
stage that reads the mainframe file, a stage that parses and validates records,
and a stage that writes to BigQuery and emits reconciliation. You can declare them
in any order; the framework works it out from the input/output edges.

### `runOnDataflow()`: the submission

`runOnDataflow(DataflowPipelineOptions options)` (lines 230–248) is the convenience
method for production submission:

```java
public PipelineResult runOnDataflow(
        DataflowPipelineOptions options, RuntimeContext context) {
    Objects.requireNonNull(options, "options must not be null");
    Objects.requireNonNull(context, "context must not be null");
    options.setRunner(DataflowRunner.class);
    org.apache.beam.sdk.Pipeline beam = buildBeam(options, context);
    return beam.run();
}
```

It sets `DataflowRunner.class` on the options (overriding whatever was previously
set), builds the Beam pipeline, and submits. The returned `PipelineResult` is
typically a `DataflowPipelineJob`; calling `waitUntilFinish()` on it blocks until
the job completes. The options carry `project`, `region`, `stagingLocation`, and
everything else Dataflow needs — those come from the caller, not from this class.

One thing worth noting: the class Javadoc's comment at lines 39–43 describes
stages as wrapped in `Create.empty(...)` placeholders. That description is stale —
the current implementation uses `Create.of(TRIGGER_TOKEN)` (a single-element
collection, not empty) to guarantee exactly-once execution. The Javadoc reflects
an earlier implementation. The code is authoritative.

## `StageTransform`: the Beam adapter

`StageTransform`\index{StageTransform} is the piece that makes each `PipelineStage` legible to
Beam. The full source is in
`data-pipeline-gcp-dataflow-java/src/main/java/com/enrichmeai/culvert/gcp/dataflow/StageTransform.java`.

The class signature (line 111) is `PTransform<PBegin, PDone>`:

```java
public final class StageTransform extends PTransform<PBegin, PDone> {
```

This shape is deliberate. `PipelineStage#execute()` is `void` and side-effecting
— it reads and writes through the `RuntimeContext` adapters, it does not map a
`PCollection` of elements. So the transform does not consume or produce a typed
`PCollection`; it is rooted at `PBegin` (the Beam pipeline's start) and
terminates at `PDone`. Its single job is to trigger the stage exactly once when
the Beam pipeline runs (StageTransform.java:23–39).

The `expand()` method (lines 145–153) shows the mechanism:

```java
@Override
public PDone expand(PBegin input) {
    PCollection<String> trigger = input.apply(
            "Trigger[" + stage.name() + "]", Create.of(TRIGGER_TOKEN));
    trigger.apply(
            "Execute[" + stage.name() + "]",
            ParDo.of(new ExecuteStageFn(stage, context, null)));
    return PDone.in(input.getPipeline());
}
```

`Create.of(TRIGGER_TOKEN)` produces a one-element collection. `ParDo.of(new
ExecuteStageFn(...))` processes that one element. `ExecuteStageFn#processElement()`
calls `stage.execute(context)`. One element in, one `execute()` call, done. A
`@Setup` or `@StartBundle` hook was considered and rejected because those fire
per-worker-instance or per-bundle, and a runner may create several of each —
which would run the stage more than once (StageTransform.java:44–49).

### Serialisation

Beam serialises a `DoFn` to its workers. Both the `PipelineStage` and the
`RuntimeContext` are captured in `ExecuteStageFn`, so both must be `Serializable`
at runtime (StageTransform.java:200–210). `DefaultRuntimeContext` is. Stub and
adapter stages used in production are expected to be. A stage that closes over
non-serialisable state cannot run on a distributed runner regardless of this
transform — the failure surfaces at `run()` time, which is the right place for
it. The serialisation round-trip is proven in
`StageTransformInstrumentationTest.java` (lines 13, 26–27) using Beam's own
`SerializableUtils.ensureSerializable` utility.

### Auto-instrumentation

Every stage execution is automatically wrapped with three observability
concerns (StageTransform.java:60–103; `ExecuteStageFn#processElement()`,
lines 246–308):

**MDC population.** Before calling `execute()`, the three Culvert MDC keys —
`run_id`, `stage_name`, `pipeline_id` — are written to the current thread's
SLF4J MDC (lines 248–256). This means every log line emitted inside the stage
automatically carries the three context fields. They are cleared in the `finally`
block so they never leak to another stage or thread.

```java
MDC.put(MDC_RUN_ID, runId);
MDC.put(MDC_STAGE_NAME, stageName);
MDC.put(MDC_PIPELINE_ID, pipelineId);
```

**Trace span.** An `ObservabilityHook.Span` named `culvert.stage/<stage-name>`
is opened before `execute()` and closed in `finally`. If the stage throws, the
exception is recorded on the span before being re-thrown (lines 276–283):

```java
ObservabilityHook.Span span = obs.span("culvert.stage/" + stageName);
span.setAttribute("culvert.run_id", runId);
try {
    stage.execute(context);
} catch (RuntimeException e) {
    span.recordException(e);
    errorCount = 1L;
    throw e;
} finally {
    ...
    span.close();
}
```

**Stage metrics.** In the `finally` block, `StageMetricsHook#recordStageMetrics()`
is called with a `StageMetrics` record carrying `pipelineId`, `runId`,
`stageName`, `rowsProcessed`, `stageLatencyMs`, and `errorCount` (lines 294–300):

```java
metricsHook.recordStageMetrics(new StageMetrics(
        pipelineId,
        runId,
        stageName,
        ROWS_PROCESSED_UNKNOWN,
        (double) elapsedMs,
        errorCount));
```

The `ROWS_PROCESSED_UNKNOWN` sentinel (lines 199–199, value `0L`) deserves a
word. Because `PipelineStage#execute()` is `void`, the framework has no way to
know how many records the stage processed. A real row count would require
element-level `PCollection` translation — which is explicitly deferred. In the
meantime, `0L` is the only Cloud Monitoring-valid value for a `CUMULATIVE INT64`
metric (negative values are rejected by the API). The sentinel is documented and
tested explicitly; it is not a silent hard-code.

Both hooks — `ObservabilityHook` for spans and `StageMetricsHook` for the three
standard metrics — are resolved worker-side from the `RuntimeContext`, never
captured at construction time (lines 260–271). This mirrors the T10.6 pattern:
`DefaultRuntimeContext`'s adapter registry is `transient` and rebuilt from
`AutoConfig.discover()` after Beam deserialisation. No extra serialised state is
added to the `DoFn`.

The two hooks have distinct concerns (StageTransform.java:79–92):
`ObservabilityHook` is the general-purpose primitive surface — arbitrary span
names, arbitrary attributes. `StageMetricsHook` is the typed Culvert-specific
seam that emits exactly the three standard metrics (`rows_processed`,
`stage_latency_ms`, `error_count`) with the fixed label schema. They coexist;
they do not duplicate each other.

## Wiring it up: HDR/TRL as a three-stage pipeline

To make the abstraction concrete, here is how the HDR/TRL mainframe ingestion
problem would be expressed in Culvert's Java layer today. The stage
implementations are not shipped by the framework — they are the application
code that sits on top of the bridge. But the wiring is exactly this:

```java
PipelineStage readStage = new HdrTrlReadStage(
    "hdr-trl-read", inputUri, List.of(), List.of("envelope", "rows"));

PipelineStage validateStage = new SchemaValidateStage(
    "validate", schema, List.of("rows"), List.of("valid-rows", "invalid-rows"));

PipelineStage writeStage = new BigQueryWriteStage(
    "bq-write", dataset, table, errorBucket,
    List.of("valid-rows", "invalid-rows"), List.of());

DataflowPipeline pipeline = new DataflowPipeline(
    "customers-ingest",
    List.of(readStage, validateStage, writeStage));

DataflowPipelineOptions options = PipelineOptionsFactory
    .as(DataflowPipelineOptions.class);
options.setProject("my-gcp-project");
options.setRegion("europe-west2");
options.setStagingLocation("gs://my-bucket/staging");

pipeline.runOnDataflow(options).waitUntilFinish();
```

`pipeline.validate()` (called inside `runOnDataflow`) checks the graph: every
input has a producer, there are no cycles, stage names are unique. `buildBeam()`
converts it to a Beam pipeline with three `StageTransform` instances applied in
topological order. `DataflowRunner` submits the job. Each stage's `execute()`
call is automatically traced, metrically recorded, and MDC-annotated.

The stage implementations themselves — reading from GCS, parsing HDR/TRL,
validating records against a schema, routing good/bad rows, writing to BigQuery
— are the application's concern. The framework provides the infrastructure that
makes those implementations observable, ordered, and cloud-portable.

## Honest status

`data-pipeline-gcp-dataflow-java` is built and tested. The two production classes
— `DataflowPipeline` and `StageTransform` — are complete and covered by four test
files (`DataflowPipelineTest`, `DataflowPipelineExecutionTest`,
`StageTransformInstrumentationTest`, `DefaultRuntimeContextWiringIT`).

The things that are not yet done:

- **Element-level `PCollection` translation.** `StageTransform` triggers `execute()` once via a single-element `Create.of`. A future sprint will add the element-level bridge that maps `Transform<V,W>` to a proper `DoFn<V,W>`, allowing Beam to fuse and parallelise data flow between stages.
- **`rowsProcessed` is always `0L`.** Until element-level translation lands, the metric is the documented `ROWS_PROCESSED_UNKNOWN` sentinel.
- **Nothing is published.** The framework is built and held. Coordinated publication to Maven Central (Java) and PyPI (Python) is future work.

These are honest gaps. The architecture is built to close them incrementally; the
contracts are the reason the gaps are closeable without breaking anything
downstream.

\begin{takeaways}
\textbf{Key takeaways}
\begin{itemize}
  \item Execution is Java's lane because the 2--3\texttimes{} Dataflow throughput-per-dollar advantage over Python Beam becomes real money above roughly 500 million rows per day, and mainframe operations culture is Java-oriented. The decision is in the division-of-labour table; this chapter is its implementation.
  \item \texttt{DataflowPipeline} implements the scheduler-agnostic \texttt{Pipeline} contract and adds two utilities: \texttt{buildBeam()} (which topologically sorts stages and applies one \texttt{StageTransform} per stage) and \texttt{runOnDataflow()} (which sets \texttt{DataflowRunner}, builds, and submits). Declaration order is irrelevant; execution order derives from input/output edges.
  \item \texttt{StageTransform} bridges \texttt{PipelineStage} to Beam as a \texttt{PTransform<PBegin,PDone>}: a one-element \texttt{Create.of} trigger drives a single \texttt{DoFn\#processElement} call, invoking \texttt{execute()} exactly once. Element-level \texttt{PCollection} mapping -- bridging \texttt{Transform<V,W>} into a proper \texttt{DoFn<V,W>} -- is explicitly deferred.
  \item Every stage execution is automatically wrapped with MDC population (\texttt{run\_id}, \texttt{stage\_name}, \texttt{pipeline\_id}), a trace span via \texttt{ObservabilityHook}, and the three standard Culvert metrics (\texttt{rows\_processed}, \texttt{stage\_latency\_ms}, \texttt{error\_count}) via \texttt{StageMetricsHook}. No stage author has to wire any of this; it is invisible infrastructure.
\end{itemize}
\end{takeaways}

\newpage

# Streaming and Batch: Choosing the Mode

One of the questions I get asked earliest and answer most often is: *should this be streaming or batch?* Teams reach for streaming because it sounds modern, then spend a year operating a real-time system to satisfy a report nobody reads before 9 a.m. So let me give you the framing I actually use — and the good news is that in Culvert the choice is smaller than it looks, because it lives at the *contract* level, not in your business logic.

## The same contracts serve both

A Culvert pipeline reads through a `Source`, transforms through `Transform`, and writes through a `Sink`. Those contracts (`data-pipeline-core-java/.../contracts/Source.java`, `Sink.java`, `Transform.java`; Python mirrors in `contracts/source.py`) say nothing about *when* records arrive. A `Source` yields records; whether it yields a bounded file this morning or an unbounded subscription forever is a property of the *adapter*, not the contract. That is the whole trick, and it is why the mode decision does not rewrite your transforms.

- **Batch**, on GCP, is a bounded read: `GcsBlobStore` (`data-pipeline-gcp-gcs`) hands you an object; the pipeline runs to completion and stops.
- **Streaming**, on GCP, is an unbounded read: `PubSubSource` (`data-pipeline-gcp-pubsub`) yields messages as they arrive; `PubSubSink` publishes them. The pipeline stays up.

Both flow through the *same* `Transform`. If you wrote your validation and mapping against the contract — as Culvert pushes you to — swapping a batch source for a streaming one does not touch it. `DataflowPipeline` (`data-pipeline-gcp-dataflow-java`) runs either bounded or unbounded graphs on the same Beam model.

## How to actually choose

I decide on four questions, in order:

1. **What does the consumer need?** If the downstream report, model, or decision is consumed daily, you need daily data. Latency you do not consume is latency you pay for and waste. Most enterprise data-to-BigQuery work is batch and should stay batch.
2. **How does the source produce?** A mainframe that drops a file at 02:00 is batch at the source; wrapping it in streaming buys you nothing but a standing bill. An event bus that emits continuously is streaming at the source; forcing it into a nightly batch loses the point.
3. **What is the cost curve?** Batch is cheap-per-run and idle the rest of the day. Streaming is a standing cost — workers up 24/7, per-message overhead. Culvert's `FinOpsSink` and the per-service cost trackers (Chapter [Cost and FinOps]) let you put a real number on both before you commit; do that, not a vibe.
4. **What is the failure model you can live with?** Batch fails a run and you re-run it — simple, auditable, a clean `run_id` per attempt. Streaming fails a *record* and you need dead-letter handling, watermarks, and replay. That operational weight is the real price of streaming, more than the compute.

## The honest default

Start batch. Move to streaming only when a question above forces it — a genuinely continuous source, or a consumer that genuinely needs sub-hour latency. The contract seam means that migration, when it comes, is an adapter swap and an execution-mode change, not a rewrite. That is exactly the position you want to be in: the decision stays reversible.

\begin{takeaways}
\textbf{Key takeaways}
\begin{itemize}
  \item In Culvert the batch-vs-streaming choice lives in the \emph{adapter} and execution mode, not the business logic — the same \texttt{Source}/\texttt{Sink}/\texttt{Transform} contracts serve both.
  \item GCP: batch = a bounded \texttt{GcsBlobStore} read; streaming = an unbounded \texttt{PubSubSource}. Both run on the same \texttt{DataflowPipeline}.
  \item Choose on consumer need, source shape, cost curve, and failure model — in that order. Latency you do not consume is wasted spend.
  \item Default to batch; move to streaming only when a real requirement forces it. The contract seam keeps that migration an adapter swap, not a rewrite.
\end{itemize}
\end{takeaways}

\newpage

# Chapter 10 — Transformation: dbt (Reused Across Languages)

There is a question that comes up every time I explain Culvert's division of labour
to someone new: "So the Java side does Beam, the Python side does Airflow, where
does the transformation live?" And the answer — "neither; it lives in dbt, and
neither language owns it" — is always the one that makes people stop and think.

That is the point of this chapter. The transformation layer is the place in Culvert
where we deliberately chose *not* to write language-specific code. The macros in
`data-pipeline-transform` are SQL. They run inside dbt's compiler. They do not
import `apache_beam`. They do not import `apache_airflow`. They are not a Java
module and they are not a Python module in any meaningful runtime sense — they are
a dbt macro library, packaged as a Python distribution only so that `pip install`
and a `packages.yml` reference can pull them into a deployment project. The actual
execution surface is BigQuery SQL, generated at dbt compile time.

This is reuse in the most literal sense. You do not reimplement transformation
logic in Java and then reimplement it again in Python. You write it once in SQL,
wrap it in dbt macros, and every deployment — whatever language mix it uses — gets
the same behaviour.


## Why dbt, and why no Java transform module

There are two places you can put post-ingestion transformation logic in a pipeline:
in code (Beam jobs, stored procedures, bespoke SQL scripts scattered through a repo)
or in dbt. For most analytical use cases, dbt wins. The reasons are not exotic:
versioned SQL, documented lineage, automated tests, incremental materialisation, and
a deployment artefact that is far easier to audit than a 3,000-line Beam transform.

But the deeper reason, in Culvert's case, is the language-neutrality question. When
we laid out the division of labour in `docs/framework-evolution/13-python-parity-release.md`,
we wrote the transformation row in the strategy table explicitly:

> **dbt / transform — Reuse (language-neutral). It's SQL + macros, not "Java" or
> "Python". `data-pipeline-transform` is Python-packaged but the assets are dbt;
> there is deliberately *no* Java transform module.**

That sentence was not an accident. Early on, there was a temptation to write a
Java-side transformation abstraction — something that would let you express
ODP-to-FDP logic in a `StageTransform` implementation and have it run on Dataflow.
We resisted it. Dataflow is for moving data. dbt is for reshaping it. Mixing the
two produces jobs that are expensive to run, painful to test, and opaque to anyone
who wants to understand the data model. dbt gives you a SQL file per model, a
`schema.yml` for tests, and a lineage graph that any analyst can read. A Beam
transform gives you Java.

The pyproject.toml for `data-pipeline-transform` makes the dependency boundary
explicit (`data-pipeline-libraries/data-pipeline-transform/pyproject.toml:8`):
`dbt-bigquery>=1.5.0` is the only non-framework dependency. The SPEC.md opens with
the same rule as a hard constraint (`SPEC.md:5`): "MUST NOT import `apache_beam`
or `apache_airflow`."


## The ODP-to-FDP journey

In Culvert's data model, data lands from ingestion into the Operational Data
Platform (ODP) — raw BigQuery tables written by the Beam jobs. The ODP is
deliberately low-ceremony: columns keep the names they arrived with, types are
widened to accommodate schema drift, and every row carries `run_id` and
`source_file` provenance from the ingest side.

The Financial Data Platform (FDP) is what the business actually queries. It is
clean, typed, masked, audited, and organised by domain. The transformation layer
is the bridge between the two.

dbt owns that bridge. The transformation flow, as the README describes it
(`README.md:52–77`), is:

```
BigQuery ODP                   dbt                      BigQuery FDP
────────────                   ───                      ────────────

Raw tables      ┌───────────────────────────────────┐
(from Beam)     │  1. Staging Models                │
     │          │     {{ source('odp', 'table') }}  │
     └─────────►│     • Clean data types            │
                │     • Apply naming conventions    │
                │                                   │
                │  2. Add Audit Columns             │
                │     {{ add_audit_columns() }}     │────► FDP Tables
                │  3. Apply PII Masking             │
                │     {{ mask_pii(col, type) }}     │
                │  4. Business Logic                │
                │     • JOINs (multi-source → 1)   │
                │     • MAPs (1:1 column rename)    │
                └───────────────────────────────────┘
```

Staging models are views, one per ODP table. They deal with the mechanical work:
renaming columns into snake\_case, casting strings to proper types, trimming padded
fields. Every staging model is `materialized='view'` — cheap, no storage cost,
always current.

FDP models are tables. They are incremental where the data volume justifies it.
They are where JOIN vs MAP matters.


## The MAP pattern

A MAP model is one-to-one: one ODP source, one FDP table. It does not wait for
anything else to finish. It fires as soon as its source is loaded.

The pattern is the simpler of the two, and that simplicity is exactly its value.
A MAP model can be incremental with a clean `is_incremental()` guard:

```sql
SELECT
    account_id,
    decision_type,
    decision_date,
    amount,
    {{ add_audit_columns() }}
FROM {{ ref('stg_decision') }}
WHERE
    {% if is_incremental() %}
      _run_id > (SELECT MAX(run_id) FROM {{ this }})
    {% endif %}
```

Two things are worth noting. First, the `{{ add_audit_columns() }}` macro expands
to three columns — `run_id`, `processed_timestamp`, and `source_file` — injected
from dbt variables at compile time (the exact expansion is in
`audit_columns.sql:12–14`):

```sql
, '{{ var("run_id") }}' as run_id
, current_timestamp() as processed_timestamp
, '{{ var("source_file") }}' as source_file
```

The `run_id` variable is the pipeline run identifier passed from the Airflow DAG
or from `dbt run --vars`. It is the lineage anchor. That single value ties this
FDP row back to the Dataflow job that wrote the ODP row that produced it.

Second, the incremental materialisation means dbt processes only the rows loaded
since the last run. For a daily full-load table of several million rows, this
transforms a multi-minute full scan into seconds. If the data fits the pattern —
monotonically increasing `run_id`, no late-arriving corrections — always prefer MAP.


## The JOIN pattern

A JOIN model combines two or more ODP sources into a single FDP table. The
archetypal example is any model that enriches an event record with entity metadata:
accounts joined to customers, transactions joined to products.

```sql
SELECT
    a.account_id,
    a.customer_id,
    c.full_name,
    c.postcode,
    a.event_type,
    a.event_amount,
    a.event_date,
    {{ mask_pii('c.full_name', 'FULL') }} AS full_name_masked,
    {{ add_audit_columns() }}
FROM {{ ref('stg_accounts') }} a
LEFT JOIN {{ ref('stg_customers') }} c
    USING (customer_id)
WHERE
    {% if is_incremental() %}
      a._run_id > (SELECT MAX(run_id) FROM {{ this }})
    {% endif %}
```

The architectural wrinkle with JOIN models is that they depend on multiple upstream
ingestion runs completing successfully. Run the transformation before both source
tables are loaded and you get a subtly wrong output — the join finds no matches, or
finds yesterday's customer record attached to today's account event. In the worst
case, nobody notices until a regulator does.

This is what the orchestration layer's dependency-checking handles. The
transformation DAG does not fire a JOIN model until every constituent ODP source
has confirmed completion. That concern belongs in Chapter 11. What matters here is
that dbt itself is innocent — it executes the SQL you give it. The guarantee that
the input is ready comes from outside.

MAP models are cheap, simple, and easy to reason about. JOIN models are powerful
and carry an orchestration debt. Use MAP wherever the data fits; use JOIN only when
the business logic genuinely requires combining sources.


## The macro library: what is actually there

Let me be precise about what the `data-pipeline-transform` package actually
contains, because the SPEC and the v1 narrative diverge slightly on naming. The
SPEC is the contract; the SQL files are the implementation.

### `add_audit_columns()`

Defined in `audit_columns.sql:11–15`. Injects three lineage columns into any
SELECT:

| Column | Type | Value source |
|--------|------|--------------|
| `run_id` | STRING | `var("run_id")` — pipeline run identifier |
| `processed_timestamp` | TIMESTAMP | `current_timestamp()` — dbt invocation time |
| `source_file` | STRING | `var("source_file")` — source GCS path |

Both `run_id` and `source_file` are required dbt variables (`SPEC.md:196–204`).
A model that omits them will fail at compile time with a dbt variable-not-found
error, which is exactly the right failure mode: the audit trail is non-negotiable.

There is also `apply_audit_columns(relation)` (`audit_columns.sql:19–32`), a DDL
macro that retroactively adds the three columns to an existing table using
`ADD COLUMN IF NOT EXISTS`. It is idempotent — safe to run against a table that
already has the columns.

### `mask_pii(column, pii_type)` and the masking family

Defined in `pii_masking.sql:88–104`. The top-level macro resolves the correct
masking strategy based on two inputs: the `pii_type` string argument and the
environment-derived masking level from `get_masking_level()`.

The masking level logic is environment-aware (`pii_masking.sql:168–180`). In a
`prod` dbt target, the level is `FULL`. In `staging`, it is `PARTIAL`. In any
other target (local development), it is `NONE` — no masking applied, so developers
can see actual data in their own sandboxes. The level can also be overridden
explicitly via `var('masking_level', 'AUTO')`.

The masking strategies available, all of which are delegated to by `mask_pii`:

- **`mask_full(column, mask_char='*')`** (`pii_masking.sql:15–17`): replaces every
  character with `mask_char` using `RPAD`. Length-preserving.
- **`mask_partial_last4(column)`** (`pii_masking.sql:27–35`): shows the last four
  characters, masks the rest. For inputs of four characters or fewer, returns the
  value unchanged.
- **`mask_redacted(column)`** (`pii_masking.sql:21–23`): returns the constant
  string `'REDACTED'` regardless of input length or content.
- **`mask_with_suffix(column, suffix_length=4, mask_pattern='XXX-XX-')`**
  (`pii_masking.sql:54–59`): for identifiers where the suffix carries utility
  (SSNs, national ID numbers), shows the last `suffix_length` digits prefixed with
  `mask_pattern`.
- **`mask_email(column, mask_prefix='****')`** (`pii_masking.sql:63–71`): keeps
  the domain, masks the local part.
- **`mask_phone_generic(column, prefix_length=3, suffix_length=4)`**
  (`pii_masking.sql:75–84`): keeps a configurable prefix and suffix, masks the
  middle.

The routing logic in `mask_pii` (`pii_masking.sql:94–103`):

| `pii_type` | Strategy | Example |
|-----------|----------|---------|
| `SSN`, `ID_SUFFIX` | `mask_with_suffix` | `XXX-XX-6789` |
| `EMAIL` | `mask_email` | `****@example.com` |
| `PHONE` | `mask_phone_generic` | `+44-***-6789` |
| `FULL` | `mask_full` | `*********` |
| `REDACTED` | `mask_redacted` | `REDACTED` |
| `PARTIAL` | `mask_partial_last4` | `*****6789` |
| Unknown | pass-through | unchanged |

One design point worth calling out: masking is driven by `pii_type` in the
model's SELECT, not by field name. The library does not make assumptions about what
a column called `ssn` contains. You have to tell it. That is a deliberate choice
— it keeps the macro library generic (`SPEC.md:23–24`: "MUST NOT reference
entity-specific field names").

The schema-level metadata that decides *which* fields get which `pii_type` lives
in the deployment's `EntitySchema` definition (`README.md:142–155`):

```python
CustomerSchema = EntitySchema(
    entity_name="customers",
    fields=[
        SchemaField(name="customer_id", field_type="STRING", required=True),
        SchemaField(name="ssn", field_type="STRING", is_pii=True),
        SchemaField(name="dob", field_type="DATE", is_pii=True),
    ],
    primary_key=["customer_id"]
)
```

The schema lives in the Python core; the macro library reads the `pii_type` you
pass as an argument. The connection between the two is the model author's
responsibility — which is the honest trade-off. Fully automatic schema-driven
masking would require the macro to query the schema at compile time. What we have
instead is a clear contract: the schema tells you which fields are PII; you pass
that information into `mask_pii()` in your SQL.

### `validate_no_pii_in_export(table, checks)`

Defined in `pii_masking.sql:129–163`. This is a safety-gate macro. It queries the
target table at dbt runtime and verifies that the specified columns actually contain
masked values. Any unmasked values found cause `exceptions.raise_compiler_error` —
a hard failure, not a warning. The default checks look for `masked_id` and
`email_address` columns; deployments can supply their own check list.

This is the one place the library actively guards against human error in the model
layer. It is not sufficient to call `mask_pii()` — you still have to call it
correctly, with the right `pii_type`. The validator does not know about `pii_type`;
it only knows whether the values in the output column look masked. Think of it as
a belt to go with the braces.

### `apply_enrichment(rules)`

Defined in `enrichment.sql:16–48`. A configuration-driven enrichment macro. You
pass a list of rule dictionaries; the macro emits the corresponding SQL expressions:

| Rule type | What it emits |
|-----------|--------------|
| `DATE_PARTS` | `EXTRACT(YEAR …)`, `EXTRACT(MONTH …)`, `EXTRACT(DAY …)`, `FORMAT_DATE('%A' …)` |
| `BUCKET` | A `CASE WHEN … THEN …` expression categorising numeric ranges |
| `LOOKUP` | A `CASE column WHEN '…' THEN '…'` code-to-description mapping |
| `EXPRESSION` | An arbitrary SQL expression you supply |

The enrichment macro keeps derived columns out of the model's main SELECT logic.
Instead of writing four EXTRACT calls and a CASE statement inline, you write:

```sql
{{ apply_enrichment([
    {'column': 'app_date', 'type': 'DATE_PARTS', 'prefix': 'app'},
    {'column': 'score', 'type': 'BUCKET',
     'buckets': {'<600': 'Poor', '600-700': 'Fair', '>700': 'Good'},
     'target': 'score_category'}
]) }}
```

This keeps the model readable when enrichment rules multiply, and it keeps the
rules in one place where an analyst can change the bucket boundaries without
touching the surrounding SQL.

### Data quality macros

Defined in `data_quality_check.sql:13–120`. Four macros that run at dbt runtime:

- **`check_required_fields(table, required_fields)`**: counts nulls in the named
  fields; warns if completeness falls below `var('quality_completeness_threshold', 95)`.
- **`check_uniqueness(table, key_field)`**: warns on duplicate keys.
- **`check_value_range(table, column, min_value, max_value)`**: warns on
  out-of-range numerics.
- **`check_freshness(table, timestamp_column, max_age_hours)`**: warns when the
  most recent timestamp is older than the threshold.

All four warn rather than error. The hard stop lives in `validate_no_pii_in_export`.
Data quality is advisory; PII exposure is not.


## The reuse argument, made concrete

Let us put the division-of-labour table from
`docs/framework-evolution/13-python-parity-release.md:20–26` into plain English:

- The Beam execution layer is Java. There is no Python Beam port — it would be
  the same amount of work for no additional value, given that Dataflow runs Java
  jobs perfectly well.
- The Airflow orchestration runtime is Python. There is no Java Airflow operator
  implementation — the Python SDK is what Airflow speaks.
- The dbt transformation layer is **neither**. It belongs to both runtimes by
  belonging to neither of them.

When a new deployment project arrives, it picks up `data-pipeline-transform` via a
single line in its `packages.yml` (`SPEC.md:183–186`):

```yaml
packages:
  - local: ../../gcp-pipeline-libraries/data-pipeline-transform
```

From that point, `add_audit_columns()`, `mask_pii()`, `apply_enrichment()`, and
`validate_no_pii_in_export()` are available in every model. No per-language SDK to
import. No interface to implement. Just SQL macros compiled by dbt and executed by
BigQuery.

That is the design. Build the transformation layer once, in the right language for
the job (SQL), and reuse it everywhere.


## Honest status

`data-pipeline-transform` is packaged at version `0.1.0` (`pyproject.toml:7`),
consistent with the rest of the Culvert distributions — the first release is
`0.1.0`, not yet API-frozen at 1.0. It is built and
held. It has not been published to PyPI under the `culvert` name. That publish
gates on the coordinated Java-and-Python `0.1.0` release — Maven Central and PyPI
together, Joseph-triggered, irreversible.

Until that gate opens, the library is available to internal deployments via the
local-path reference in `packages.yml`. Macro unit tests run via pytest
(`tests/unit/test_pii_macros.py`, `tests/unit/test_macros_rendered.py`) against a
mock dbt project in `tests/unit/dbt_test_project/`. The test coverage is honest: it
verifies compiled SQL output, not BigQuery execution. End-to-end validation happens
when the transformation DAG runs against a real ODP dataset.

The SPEC notes two gaps that remain open. The environment-awareness in
`get_masking_level()` works correctly; what the library does not yet provide is a
helper for partition-pruning beyond the standard `is_incremental()` block, which
means wide incremental JOIN models can still be expensive on a historical
correction. And there is no standard playbook for full-refresh recovery on a
multi-year JOIN table. Both are known; neither has a ticket. If you are running
Culvert on a dataset where historical corrections are common, keep them in mind.


\begin{takeaways}
\textbf{Key takeaways}
\begin{itemize}
  \item dbt is the transformation layer for Culvert not because it was convenient,
    but because SQL is language-neutral. There is deliberately no Java transform
    module and no Python transform module — only macros that compile to BigQuery SQL.
  \item The MAP pattern (one ODP source, one FDP table) fires immediately and can
    be fully incremental. The JOIN pattern (multiple ODP sources, one FDP table)
    waits for every constituent; the orchestration layer enforces that dependency.
    Confusing them produces subtly wrong data, not an obvious failure.
  \item \texttt{add\_audit\_columns()} injects three lineage columns — \texttt{run\_id},
    \texttt{processed\_timestamp}, \texttt{source\_file} — into every FDP row. The
    \texttt{run\_id} is a required dbt variable; a model that omits it fails at
    compile time. End-to-end lineage is then a single join on \texttt{run\_id}.
  \item \texttt{mask\_pii(column, pii\_type)} is environment-aware: full masking
    in prod, partial in staging, no masking in dev. Add a new PII field; pass the
    right \texttt{pii\_type}; the correct strategy is applied automatically.
  \item \texttt{validate\_no\_pii\_in\_export} is the belt to go with the braces —
    it raises a compiler error if unmasked values are found in the output table,
    guarding against a model that calls \texttt{mask\_pii()} with the wrong type or
    not at all.
  \item The library is built and held at \texttt{0.1.0}. It publishes to PyPI as
    part of the coordinated Java-and-Python Culvert release — not before.
\end{itemize}
\end{takeaways}

\newpage

# Chapter 11 — Orchestration: A Cloud-Neutral DAG Model

The last chapter left us with a question that sounds simple until you try to answer
it: who owns the schedule? Beam knows how to move records. dbt knows how to
transform relations. Neither of them knows when to run, in what order, or what to
do when something goes wrong. That is orchestration's job, and it turns out to be
the place where the cloud-neutral / GCP-specific seam is the most
interesting to draw.

Every orchestration layer has to answer the same four questions:

- **When should a pipeline run?** On a schedule, on demand, on an event, or on a
  chain of events.
- **In what order?** Parallel where possible, sequential where required.
- **What if something fails?** Retry, quarantine, alert, page.
- **How do I know it worked?** State, history, dashboards, audit.

Airflow answers all four, which is why Culvert uses it as the reference
orchestration runtime. But the interesting decision — the one that shapes
everything else in this chapter — was made before we picked Airflow. It is the
decision about what Java owns and what Python owns.

## The model / runtime split

There is no Airflow for Java. There is no Java SDK that lets you declare DAGs
natively, register tasks, or push a scheduler configuration. If you want to
author an Airflow DAG, you write Python. That fact sounds like a constraint.
In Culvert, it became a design decision.

The Java side owns the **model**: an immutable, scheduler-agnostic description of
what a pipeline is and how its stages depend on each other. The Python side owns
the **runtime**: the operators, sensors, hooks, and DAG factory that execute those
stages in a real Airflow environment.

This is not a polyglot contortion. It is the natural conclusion of the contract
principle from Chapter 5. A `Pipeline` is a language-neutral description of a
computation graph. The orchestration layer takes that description, translates it
into a target-scheduler representation, and hands it off to a runtime that knows
nothing about the original Java pipeline. Each side does what it is uniquely
suited for.

## The Java model layer

The Java model layer lives in
`data-pipeline-libraries-java/data-pipeline-orchestration-java/`. Three classes
and one interface carry the entire design.

### `DagSpec` — the scheduler-agnostic DAG

\index{DagSpec}`DagSpec` is described in its own Javadoc as "an immutable,
scheduler-agnostic description of a directed acyclic graph derived from a Culvert
`Pipeline`." The key phrase is *without importing any of those engines* — the goal
is to capture the full structure needed to submit a pipeline to any task-scheduler
(Airflow, Cloud Composer, AWS Step Functions, or any future target) using nothing
but `java.util`:

```java
// data-pipeline-orchestration-java/.../orchestration/DagSpec.java:35-36
public final class DagSpec implements Serializable {
    // dagId, schedule, tasks (List<TaskSpec>), edges (List<Edge>)
}
```

Four fields, all immutable, all defensively copied:

- `dagId` — the unique scheduler identifier.
- `schedule` — an opaque string (`"@daily"`, `"0 6 * * *"`, or `null` for
  manually triggered DAGs). The model does not parse this; renderers do.
- `tasks` — one `TaskSpec` per pipeline stage, in topological order.
- `edges` — explicit `(fromTaskId → toTaskId)` pairs, redundant with the
  adjacency list in `TaskSpec` but provided for renderers that prefer an edge
  list.

The nested `Edge` class (`DagSpec.java:45-96`) is deliberately minimal — just
two validated, non-blank `String` fields and value-equality semantics. Nothing
about Airflow, nothing about GCP.

### `TaskSpec` — one unit of work

\index{TaskSpec}`TaskSpec` (`TaskSpec.java:31`) maps one `PipelineStage` to one
scheduler task. The `taskId` equals the stage name; `stageName` is kept
explicitly for forward-compatibility. `upstreamTaskIds` carries the dependency
list; `params` carries an opaque, serialisable `Map<String, Serializable>` for
renderer-specific configuration. In the current translator, `params` is always
`Map.of()` — the structural skeleton carries no cloud-specific payload:

```java
// data-pipeline-orchestration-java/.../orchestration/TaskSpec.java:53-71
public TaskSpec(String taskId,
                String stageName,
                List<String> upstreamTaskIds,
                Map<String, Serializable> params) { … }
```

Instances are immutable. Collections are defensively copied and returned as
unmodifiable views. The same `TaskSpec` instance can be passed to an
`AirflowDagRenderer` today and, in principle, an AWS Step Functions renderer
tomorrow.

### `PipelineToDagSpec` — the translator

\index{PipelineToDagSpec}`PipelineToDagSpec` is a static utility class
(`PipelineToDagSpec.java:40`) that translates a validated `Pipeline` contract
into a `DagSpec`. The translation is purely structural:

1. Call `pipeline.validate()` — cycles, orphan inputs, and duplicate stage names
   surface as `IllegalStateException` from the contract's own validation logic.
2. Build an output-to-producer index.
3. Run Kahn's topological sort, ties broken by declaration order for
   determinism.
4. Emit `TaskSpec` and `Edge` objects in topological order.

```java
// data-pipeline-orchestration-java/.../orchestration/PipelineToDagSpec.java:66-152
public static DagSpec translate(Pipeline pipeline, String schedule) {
    pipeline.validate();
    // … Kahn's algorithm over pipeline.stages() …
    return new DagSpec(pipeline.name(), schedule, tasks, edges);
}
```

The translator has no cloud-specific imports. It depends only on
`data-pipeline-core` (for the `Pipeline` / `PipelineStage` contracts) and
`java.util`. It is the purest expression of the cloud-neutral model: given any
valid `Pipeline`, regardless of how it was built or what it will eventually run
on, produce a `DagSpec` that any compliant renderer can consume.

### `DagRenderer` — the strategy interface

\index{DagRenderer}The renderer side is a single strategy interface
(`DagRenderer.java:21`):

```java
// data-pipeline-orchestration-java/.../orchestration/DagRenderer.java:21-32
public interface DagRenderer {
    /**
     * Render the given DagSpec into a target-specific string artefact.
     * Implementations must consume only DagSpec/TaskSpec —
     * they must not reach back into the Pipeline contract or
     * any runtime dependency.
     */
    String render(DagSpec dagSpec);
}
```

Two implementations ship: `AirflowDagRenderer` for standalone Airflow
environments and `ComposerDagRenderer` for Cloud Composer. Both implement the
same interface. Both take a `DagSpec` and return a `String` — Python source code.

The `String` return type is telling. Because there is no Airflow Java library —
because the JVM cannot natively speak to an Airflow scheduler — the renderer's
output is generated Python text, not a compiled artefact or an SDK call. This
forces the clean separation. The renderer cannot accidentally reach into any
Airflow Java dependency, because no such dependency exists. The design constraint
is physically enforced by the ecosystem.

## `AirflowDagRenderer` — generating the DAG

\index{AirflowDagRenderer}`AirflowDagRenderer` targets Apache Airflow 2.9.x
(`AirflowDagRenderer.java:9`). In its base form it emits a Python DAG file using
`EmptyOperator` (the `DummyOperator` was deprecated in 2.4 and removed in 2.9):

```java
// Simplified from AirflowDagRenderer.java:166-198
lines.add("from airflow.operators.empty import EmptyOperator");
lines.add("with DAG(");
lines.add("    dag_id=\"" + dagSpec.dagId() + "\",");
lines.add("    schedule=" + scheduleValue + ",");
lines.add("    catchup=False,");
lines.add(") as dag:");
lines.add("    tasks = {}");
for (TaskSpec task : dagSpec.tasks()) {
    lines.add("    tasks[\"" + task.taskId() + "\"] = "
            + "EmptyOperator(task_id=\"" + task.taskId() + "\")");
}
for (DagSpec.Edge edge : dagSpec.edges()) {
    lines.add("    tasks[\"" + edge.fromTaskId() + "\"] "
            + ">> tasks[\"" + edge.toTaskId() + "\"]");
}
```

Task ids are referenced through a Python `dict` (`tasks["id"]`) rather than bare
variable names, so a task id that is not a valid Python identifier — a stage name
with hyphens, say — is handled safely without renaming.

The job-control wiring path (`AirflowDagRenderer.java:215-325`) replaces each
`EmptyOperator` with a `PythonOperator` whose callable wraps the task body with
job-control lifecycle calls: `create_job` on the first task, `update_status` on
entry and success, `mark_failed` in the `except` block. The status strings
(`"created"`, `"running"`, `"succeeded"`, `"failed"`) mirror the Culvert
`JobStatus` wire values — keeping the generated Python in sync with the Java
contract without importing any GCP type.

## `ComposerDagRenderer` — the GCP packaging wrapper

\index{ComposerDagRenderer}`ComposerDagRenderer` (`ComposerDagRenderer.java:75`)
wraps `AirflowDagRenderer` rather than duplicating it. The DAG body is identical;
the difference is a packaging header that the GCS deployment pipeline reads:

```
# Generated by Culvert ComposerDagRenderer — do not edit by hand.
# Target: Google Cloud Composer 2 (Airflow 2.9.x)
# Composer image family: composer-2-airflow-2
#
# Deploy to Cloud Composer by uploading this file to:
#   gs://<your-composer-bucket>/dags/my_dag.py
#
# Command:
#   gcloud composer environments storage dags import \
#       --environment=<ENV_NAME> --location=<REGION> \
#       --source=my_dag.py
```

The `AIRFLOW_VERSION` constant is `"2.9.x"` and `COMPOSER_IMAGE_FAMILY` is
`"composer-2-airflow-2"` (`ComposerDagRenderer.java:78-81`). These are baked into
the generated file so that operators auditing a deployed DAG can trace it to the
renderer version that produced it. No GCP SDK is imported on the Java side; the
output text references GCS paths, but they are string literals.

Usage is a single call:

```java
// AirflowDagRenderer.java:63-64
DagSpec spec = PipelineToDagSpec.translate(myPipeline, "@daily");
String pySource = new ComposerDagRenderer().render(spec);
// Upload pySource to gs://<composer-bucket>/dags/<dagId>.py
```

## The Python runtime layer

The Java model emits a structural skeleton. It is the Python side that makes the
skeleton do real work. The runtime library lives in
`data-pipeline-libraries/data-pipeline-orchestration/src/data_pipeline_orchestration/`
and is partitioned into four concerns: factories, sensors, operators, and
dependency checking.

### The DAG factory

The public entry point is a single function:

```python
# data-pipeline-orchestration/.../factories/dag_factory.py:85-143
def create_dags(config: Dict[str, Any], global_ns: Dict[str, Any]) -> None:
    """Build the full DAG set and inject it into global_ns."""
    …
    global_ns[trigger_dag.dag_id] = trigger_dag        # pubsub trigger
    for entity in entities:
        global_ns[ingestion_dag.dag_id] = ingestion_dag # per entity
    for model in fdp_models:
        global_ns[transformation_dag.dag_id] = transformation_dag  # per FDP
    global_ns[status_dag.dag_id] = status_dag           # pipeline status
```

Airflow's DagBag discovers any `DAG` object registered in module globals, so
`create_dags(config, globals())` in a file under `dags/` is all a deployment
needs. For a config with N entities and M FDP models, this registers `2 + N + M`
DAGs across four types (`dag_factory.py:141`):

1. One `{system_id}_pubsub_trigger_dag` — the event-driven entry point.
2. One `{system_id}_{entity}_ingestion_dag` per entity — runs Dataflow via
   `BaseDataflowOperator`, checks FDP readiness, triggers transformation.
3. One `{system_id}_{fdp_model}_transformation_dag` per FDP model — runs dbt
   once required ODP entities are loaded.
4. One `{system_id}_pipeline_status_dag` — daily observer that alerts if the
   pipeline is incomplete.

An error-handling DAG (a fifth builder) is reachable via `DagFactory` but is
deliberately not wired into `create_dags` (`dag_factory.py:25-28`). Separating
it means the recovery workflow can be scheduled and scaled independently of the
main pipeline lifecycle.

None of these DAGs is hand-written. The point is the same as the Java model:
reducing the editable surface to configuration. Adding a new entity is a config
change, not a Python authoring task, and definitely not an orchestration code
review.

### `BasePubSubPullSensor` — filtering before acking

\index{BasePubSubPullSensor}The library extends Airflow's built-in
`PubSubPullSensor` with a critical production detail (`sensors/pubsub.py:37`).
The base class's `poke()` acknowledges all pulled messages immediately, including
ones you do not care about. If a `.csv` notification arrives before the expected
`.ok` file, the parent acks it, returns `True`, and the sensor terminates
prematurely.

`BasePubSubPullSensor.poke()` (`pubsub.py:83-133`) overrides this: it pulls,
filters by extension first, acknowledges regardless (to clear the subscription),
but returns `False` for non-matching messages. The sensor keeps looking. Matching
messages are stashed in `self._return_value` and returned by `execute()`. The
library also pushes extracted metadata to XCom (`pubsub.py:163-171`) so
downstream tasks know which GCS path triggered the run.

The import guard pattern (`pubsub.py:27-35`) is worth noting:

```python
# sensors/pubsub.py:27-34
try:
    from airflow.providers.google.cloud.sensors.pubsub import PubSubPullSensor
    AIRFLOW_AVAILABLE = True
except ImportError:
    AIRFLOW_AVAILABLE = False
    PubSubPullSensor = object  # Stub for type hints
```

This makes the library import-safe in environments without Airflow — useful for
unit tests that want to import `EntityDependencyChecker` without pulling in the
full Airflow dependency graph. The pattern appears across
`operators/dataflow.py:42-121` as well.

### `BaseDataflowOperator` — abstracted Dataflow execution

\index{BaseDataflowOperator}`BaseDataflowOperator` (`operators/dataflow.py:195`)
wraps `DataflowStartFlexTemplateOperator` with source-type abstraction (GCS
versus Pub/Sub), processing-mode abstraction (batch versus streaming), and
template-type selection (classic versus Flex). The `DataflowJobConfig` dataclass
(`dataflow.py:138`) carries the structured configuration and its own `validate()`
before any cloud call is made.

Two convenience subclasses ship: `BatchDataflowOperator` (source `gcs`, mode
`batch`) and `StreamingDataflowOperator` (source `pubsub`, mode `streaming`). The
template fields list (`dataflow.py:232-245`) is the standard Airflow mechanism
for Jinja templating, so `project_id`, `region`, `input_path`, and friends can be
driven by Airflow Variables without any extra plumbing.

### `EntityDependencyChecker` — JOIN preconditions without sleep loops

\index{EntityDependencyChecker}The JOIN/MAP pattern that Chapter 10's dbt layer
depends on needs an answer to the question: have all the ODP entities this FDP
model requires been loaded for today's partition? `EntityDependencyChecker`
(`dependency.py:69`) answers it:

```python
# dependency.py:102-110
checker = EntityDependencyChecker(
    project_id="my-project",
    system_id="application1",
    required_entities=["customers", "accounts"],
)
if checker.all_entities_loaded(extract_date):
    trigger_transformation()
```

`all_entities_loaded()` (`dependency.py:175`) queries the job-control store for
the latest status per entity for the given extract date and checks that all
required entities are in a success state. No sleep loops. No deadlocks. In a DAG
context this becomes a `ShortCircuitOperator`: if not all entities are ready, the
transformation is skipped this run and reattempted on the next schedule.

One thing to be honest about: as at Culvert 0.1.0, the fallback path in
`EntityDependencyChecker.__init__()` still lazy-imports `gcp_pipeline_core`
(`dependency.py:144`) when no `job_repo` is injected. The Culvert
`JobControlRepository` Protocol exists; the concrete BigQuery adapter has not yet
migrated from the predecessor library. The in-code note (`dependency.py:29-64`)
documents the mismatch: the legacy status value is `"SUCCESS"` (uppercase); the
Culvert contract uses `"succeeded"` (lowercase). The migration path is written and
tracked; the step is unfinished. A caller that injects their own `job_repo`
implementation bypasses this entirely — which is the designed escape hatch.

### `SecretManagerHook` — credential access at the right layer

The `hooks/` package provides `SecretManagerHook` (`hooks/secrets.py:23`), which
wraps the Google Cloud Secret Manager client. This belongs in the orchestration
runtime layer, not in Beam jobs or dbt profiles, because Airflow is the natural
secrets boundary: the scheduler runs with appropriate GCP service-account
permissions; individual Beam workers do not need to know where their credentials
come from. The hook exposes a single `get_secret(secret_id, project_id, version_id)`
method and gracefully degrades when neither `google-cloud-secret-manager` nor the
Airflow Google provider is installed.

## When Composer is overkill

Cloud Composer 2 starts at approximately \$300 per month before a single task is
scheduled. It is a managed Airflow environment, which means it runs a GKE cluster,
a Postgres metadata database, a web server, a scheduler, and workers — all of
which you pay for around the clock, including weekends, including your team's
annual leave, including the fortnight in December when nothing is being deployed.
I have watched teams onboard Composer on week one of a new project and spend the
first three months paying for infrastructure that processes four files a day.

The `deploy_composer` flag exists precisely because of this. In the Culvert
deployment model, documented in `docs/FINOPS_STRATEGY.md`, Composer is disabled
by default. You have to pass `deploy_composer=true` explicitly — in the workflow
dispatch, or in your Terraform variables. The default is the cheaper path. The
principle is: make the expensive thing require a deliberate act.

For pipelines that do not need Composer, the alternatives are documented and
cheaper:

- **Cloud Run Jobs** for scheduled dbt runs. A `dbt run` for a small schema
  finishes in under two minutes and can be triggered on a Cloud Scheduler cron
  for approximately the cost of a coffee per month.
- **Cloud Functions** for event-driven triggers. One invocation per `.ok` file
  rather than a scheduler process that runs continuously.
- **Cloud Workflows** for sequencing, where you need DAG-like dependency
  semantics without the full Airflow machinery.

The honest question to ask before enabling Composer is: how many DAG runs per day
do I have, and how long does each task take? If the answer is "ten runs, each two
minutes", you are paying \$300/month to schedule 20 minutes of compute. Cloud Run
Jobs will cost you perhaps \$15/month for the same work. That is not a technical
argument; it is an arithmetic one.

Where Composer earns its price is at the other end of the scale: hundreds of DAG
runs per day, complex dependency graphs, teams that need the Airflow UI for
operational visibility, compliance requirements that demand a full audit trail and
SLA tracking. Below roughly twenty entities with daily loads, I would want a very
specific reason to choose Composer over Cloud Run Jobs. Above roughly fifty
entities with intra-day SLAs, Composer's scheduler performance and the Airflow UI
become genuinely valuable.

## Airflow version considerations

The renderers in Culvert 0.1.0 target **Airflow 2.9.x** with the
`composer-2-airflow-2` image family (`ComposerDagRenderer.java:78-81`). This is
the version where `DummyOperator` was fully removed (hence `EmptyOperator` in the
generated output), the `schedule=` parameter on `DAG()` replaced the deprecated
`schedule_interval=`, and the deferrable operator model matured enough to use in
production.

If you are deploying to Composer in 2026, Airflow 2.9 on Composer 2 is a
reasonable conservative choice. New projects that can start on Airflow 2.10 gain
full deferrable-operator support by default — sensors deferring their wait slots
to the triggerer rather than holding a worker slot for the duration of a long
poll. For the `BasePubSubPullSensor`, that translates directly to fewer idle
worker slots and a lower cluster footprint.

Airflow 3 is stabilising at time of writing. The renderer output would need minor
updates — the Task Execution API hardens the scheduler-worker boundary, a handful
of imports move — but the structural skeleton that `AirflowDagRenderer` generates
(`dag_id`, `schedule`, `catchup`, task dict, `>>` dependency expressions) is
stable across all Airflow 2.x and expected to remain stable in 3.x. The model
layer is unaffected regardless.

## What the skeleton looks like end to end

To make the model / runtime split concrete, here is the full path from a `Pipeline`
to a deployed Composer DAG:

**Step 1 — Java: translate**

```java
// Translate a Culvert Pipeline into a scheduler-agnostic DagSpec
DagSpec spec = PipelineToDagSpec.translate(myPipeline, "@daily");
// spec.dagId()  → pipeline.name()
// spec.tasks()  → one TaskSpec per stage, topological order
// spec.edges()  → explicit (from, to) dependency pairs
```

**Step 2 — Java: render**

```java
// Render the DagSpec as a Cloud Composer-targeted Python file
String pySource = new ComposerDagRenderer().render(spec);
// pySource begins with the Composer packaging header,
// followed by a plain Airflow 2.9.x DAG definition.
```

**Step 3 — deploy**

```bash
gcloud composer environments storage dags import \
    --environment=<ENV_NAME> --location=<REGION> \
    --source=<dagId>.py
```

**Step 4 — Python: runtime**

The deployed file is a structural skeleton — `EmptyOperator` placeholders wired
with correct `>>` dependencies. A real deployment replaces the `EmptyOperator`
instances with operators from the Python runtime library: `BaseDataflowOperator`
for ingestion tasks, dbt subprocess calls for transformation tasks,
`BasePubSubPullSensor` as the trigger. The structural skeleton provides the
DAG shape and dependency graph; the Python library provides the execution logic.

This is not magic. It is the same pattern the Spring `DataSource` auto-configuration
uses: define the contract, let the runtime supply the implementation, keep the two
concerns separate so either can change independently.

## Review: what works, what could be better

**Strengths:**

The model layer is genuinely engine-free. You can write tests against `DagSpec`
and `PipelineToDagSpec` with no Airflow on the classpath — the test suite does
exactly this. The topological sort is deterministic (ties broken by declaration
order), which matters for diff stability when you regenerate DAGs. The
`ComposerDagRenderer` reuses `AirflowDagRenderer.buildDagBody()` rather than
duplicating it; that composition is the right call.

The Python library's import-safety discipline — the `AIRFLOW_AVAILABLE` guard
pattern in `pubsub.py` and `dataflow.py` — means the library can be imported in
environments without Airflow, which unlocks testing `EntityDependencyChecker` and
`DagFactory` configuration logic without requiring a full Airflow install.

The `create_dags(config, globals())` API is minimal. One function, one call per
deployment file, no framework-specific base classes to inherit from. Adding a new
entity is a configuration change, not an orchestration code change.

**Honest gaps:**

The `params` field on `TaskSpec` is always `Map.of()` in the current translator.
The design anticipates renderer-specific configuration flowing through that map —
Dataflow template URIs, BigQuery table targets, error bucket paths. That
surface is unoccupied. It is the correct expansion point; it is not yet filled.

The `EntityDependencyChecker` legacy coupling (`dependency.py:135-150`) is
documented and tracked, but it is still there. A caller that does not inject a
`job_repo` gets a `gcp_pipeline_core` import at construction time. The migration
note in the source is clear about what needs to change; the step remains open.

The Java-generated skeleton and the Python runtime library are complementary, but
they are not wired together end to end in a single automated test. That test would
translate a `Pipeline`, render a DAG file, parse the Python, and confirm the task
ids match the stage names and the dependency edges match the `>>` expressions. It
is a straightforward integration test; it does not yet exist.

\begin{takeaways}
\textbf{Key takeaways}
\begin{itemize}
  \item There is no Airflow SDK for Java. The Java model layer (\texttt{DagSpec},
        \texttt{TaskSpec}, \texttt{PipelineToDagSpec}) is therefore a
        \emph{Python code generator}, not a scheduler client. The ecosystem
        constraint physically enforces the MODEL/RUNTIME split.
  \item \texttt{DagRenderer.render(DagSpec)} is the single seam. Implementations
        must consume only \texttt{DagSpec}/\texttt{TaskSpec}; no renderer may
        reach back into the \texttt{Pipeline} contract or any runtime dependency
        (\texttt{DagRenderer.java:7--9}).
  \item The Python runtime (\texttt{create\_dags}, \texttt{BaseDataflowOperator},
        \texttt{BasePubSubPullSensor}, \texttt{EntityDependencyChecker}) is the
        reused production layer. It is structurally independent of the Java
        skeleton: the two are complementary facets of the same architecture, not
        a pipeline of calls.
  \item Composer starts at roughly \$300/month before a single task is scheduled.
        It is disabled by default (\texttt{deploy\_composer=false}). Cloud Run
        Jobs cost roughly \$15/month for the same ten-entity, daily-schedule
        workload. Make the expensive thing require a deliberate act.
  \item \texttt{EntityDependencyChecker} with a \texttt{ShortCircuitOperator} is
        how JOIN preconditions work. No sleep loops, no deadlocks, no
        ``wait 30 minutes then give up'' anti-patterns.
  \item Culvert 0.1.0 renderers target Airflow 2.9.x / \texttt{composer-2-airflow-2}.
        The generated DAG skeleton (task dict, \texttt{>>} dependencies,
        \texttt{catchup=False}) is stable across Airflow 2.x and expected to
        survive 3.x without structural changes.
\end{itemize}
\end{takeaways}

\newpage

# Chapter 12 — Observability and Lineage

\index{observability}A lot of teams mistake "observability" for "three Cloud
Monitoring dashboards and a Slack alert". I made that mistake myself, early on.
You wire up a counter for records processed, a gauge for queue depth, and you
feel good about it. Then something goes wrong at 03:00 — a suspicious revenue
figure, a reconciliation that doesn't close — and you discover the dashboards
tell you *what* without a shred of *why*. The run that produced the bad row had
a trace ID no one wrote down. The log lines are in Cloud Logging but there's no
consistent field to filter on. The Dataflow job succeeded; the data is wrong.
Congratulations, you have three dashboards and zero observability.

Culvert's view is different. Observability means being able to answer, about any
point in the pipeline's history: *what happened, why, how much did it cost, who
was affected, and can I reproduce it?* Answering that requires a single thread of
identity — a `run_id` — that ties every log line, every metric point, every trace
span, and every lineage event to the same run. Everything else is plumbing to
get that thread into the right places.

This chapter covers the plumbing: the two observability contracts, the four GCP
adapters that implement them, the structured-log bridge that writes context into
every log line automatically, and the lineage seam that stamps Data Catalog when
a stage completes. The seams are cloud-neutral; the adapters are GCP-specific and
live behind them. Swap the adapters, keep the pipeline code, take your `run_id`
thread to AWS or Azure.

## Two seams, not one

The observability surface in Culvert v0.1.0 splits across two contracts, and the
distinction matters.

**`ObservabilityHook`** is the general-purpose primitive. It exposes five
methods: `counter`, `gauge`, `histogram`, `log`, and `span`. Pipeline code has
one dependency to inject rather than three separate objects (a metrics collector,
a logger, a tracer). The contract is defined in both Java and Python, with
identical semantics in each language.

```java
// data-pipeline-core-java: ObservabilityHook.java:20
public interface ObservabilityHook {
    void counter(String name, long value, Map<String, String> tags);
    void gauge(String name, double value, Map<String, String> tags);
    void histogram(String name, double value, Map<String, String> tags);
    void log(String level, String message, Map<String, Object> fields);
    Span span(String name);
}
```

Python mirrors it as a `@runtime_checkable` Protocol so that structural
subtyping (`isinstance` checks) works without inheritance:

```python
# data-pipeline-core: contracts/observability.py:26
@runtime_checkable
class ObservabilityHook(Protocol):
    def counter(self, name: str, value: int = 1,
                tags: Mapping[str, str] = _NO_TAGS) -> None: ...
    def gauge(self, name: str, value: float,
              tags: Mapping[str, str] = _NO_TAGS) -> None: ...
    def histogram(self, name: str, value: float,
                  tags: Mapping[str, str] = _NO_TAGS) -> None: ...
    def log(self, level: str, message: str, **fields: Any) -> None: ...
    def span(self, name: str) -> AbstractContextManager[Any]: ...
```

`ObservabilityHook` is intentionally general: arbitrary metric names, arbitrary
tags, arbitrary log fields. That generality is a feature for pipeline code that
just wants to emit something. It is a liability for the *framework* itself, which
needs to guarantee that the same three metrics appear on every stage completion
with the same label schema so Cloud Monitoring dashboards do not drift.

That is why there is a second contract.

**`StageMetricsHook`** is narrow by design. One method, one value type, three
fixed metrics, three fixed label dimensions:

```java
// data-pipeline-core-java: StageMetricsHook.java:32
public interface StageMetricsHook {
    void recordStageMetrics(StageMetrics metrics);
}
```

`StageMetrics` is a Java record
(`data-pipeline-core-java: StageMetrics.java:26`) carrying exactly
`pipelineId`, `runId`, `stageName` (the labels) and `rowsProcessed`,
`stageLatencyMs`, `errorCount` (the values). You cannot mis-name a label;
you cannot forget a field. The contract's Javadoc makes the intent explicit:
narrowness enables type-safe constructors, clear mock-based testing, and
prevents callers from accidentally creating metric series with ad-hoc label
shapes that break dashboard queries.

The two contracts live in `data-pipeline-core-java` with no GCP or Beam
imports. The GCP adapters live in `data-pipeline-gcp-observability-java`. This
is the standard Culvert layering: contracts in the neutral kernel, adapters
behind them, Beam wiring in a separate module.

## `CloudTraceObservabilityHook` — spans, metrics, and logs in one object

\index{CloudTraceObservabilityHook}The GCP implementation of `ObservabilityHook`
is `CloudTraceObservabilityHook`
(`data-pipeline-gcp-observability-java/src/main/java/com/enrichmeai/culvert/gcp/observability/CloudTraceObservabilityHook.java`).
It bridges the Culvert `ObservabilityHook` surface to OpenTelemetry.

The class deliberately does no OTel SDK wiring itself. The design note in the
Javadoc (`CloudTraceObservabilityHook.java:29`) is worth quoting:

> Wiring is decoupled from this class: callers construct an `OpenTelemetry`
> instance whose `SdkTracerProvider` has a `TraceExporter` from
> `com.google.cloud.opentelemetry:exporter-trace` registered (typically via a
> `BatchSpanProcessor`). This class wraps the resulting `Tracer` and `Meter`
> and bridges them to the Culvert `ObservabilityHook` surface.

This matches the graceful-degradation idiom I described earlier. If a full GCP
OTel SDK is wired, spans go to Cloud Trace and metrics go to Cloud Monitoring.
If only the no-op global OTel is installed — which is the default when no SDK
is on the classpath — the hook is still instantiable and every call is a
no-op. No crash, no missing dependency, no conditional import. The pipeline runs
identically; it just does not produce traces.

The three constructors reflect three use cases
(`CloudTraceObservabilityHook.java:113–143`):

```java
// No-arg: ServiceLoader / GlobalOpenTelemetry — graceful no-op if OTel absent
public CloudTraceObservabilityHook() {
    this(io.opentelemetry.api.GlobalOpenTelemetry.get(), DEFAULT_INSTRUMENTATION_SCOPE);
}

// Primary: caller supplies a configured OTel instance and pipeline name
public CloudTraceObservabilityHook(OpenTelemetry otel, String instrumentationScope) { ... }

// Test: inject pre-resolved Tracer and Meter directly
public CloudTraceObservabilityHook(Tracer tracer, Meter meter) { ... }
```

The no-arg constructor enables `ServiceLoader` discovery so Beam workers pick
up the hook automatically when the module is on the classpath — a pattern
introduced in Sprint 12 (T12.6, issue #91) and proven by
`WorkerSideHookResolutionTest.java:105`.

Internally, OTel instruments are lazily created and cached by name in
`ConcurrentHashMap`s
(`CloudTraceObservabilityHook.java:91–93`). Re-registration would be expensive
and would create duplicate metric IDs in Cloud Monitoring; the caches keep
metric identities stable across calls.

One honest rough edge: the gauges implementation uses a single-shot
`DoubleHistogram` rather than a true synchronous gauge
(`CloudTraceObservabilityHook.java:155–163`). The comment explains it:
OTel 1.38 does not have a synchronous-gauge instrument; the 1.40+ `gaugeBuilder`
API is the right fix once the SDK is bumped. The histogram workaround works
but will look odd in Cloud Monitoring — a gauge plotted as a distribution.
Something to clean up before the coordinated Maven Central release.

Spans are returned as an `OtelSpanAdapter`
(`CloudTraceObservabilityHook.java:234`), which wraps the OTel
`Span`+`Scope` pair and is idempotent on `close()`. Try-with-resources works;
double-close is a no-op rather than throwing. Lifecycle for flushing the
`BatchSpanProcessor` on shutdown belongs to whoever built the SDK — the hook
itself is not `AutoCloseable` because the wrapped `OpenTelemetry` interface
makes no lifecycle promise.

## `CloudMonitoringMetricsHook` — the typed metrics seam

\index{CloudMonitoringMetricsHook}Where `CloudTraceObservabilityHook` is
general-purpose, `CloudMonitoringMetricsHook`
(`CloudMonitoringMetricsHook.java:92`) is the typed implementation of
`StageMetricsHook`. It emits exactly three Cloud Monitoring custom metrics per
stage completion via the v3 `MetricServiceClient`:

| Metric type | Kind | Value type |
|---|---|---|
| `custom.googleapis.com/culvert/rows_processed` | CUMULATIVE | INT64 |
| `custom.googleapis.com/culvert/stage_latency_ms` | GAUGE | DOUBLE |
| `custom.googleapis.com/culvert/error_count` | CUMULATIVE | INT64 |

All three carry labels `pipeline_id`, `run_id`, `stage_name` — drawn directly
from the `StageMetrics` record. One `CreateTimeSeries` RPC carries all three
`TimeSeries` objects in a single round-trip
(`CloudMonitoringMetricsHook.java:243–255`).

The contract's resilience rule is enforced here: if the RPC fails, the
exception is caught, logged at `WARN`, and swallowed. The pipeline never stops
because Cloud Monitoring is having a bad morning. The failure count is
accessible via `monitoringFailureCount()` (`CloudMonitoringMetricsHook.java:263`)
for tests and operational alerting.

Project-ID resolution follows a three-step precedence chain
(`CloudMonitoringMetricsHook.java:167–189`):

1. System property `culvert.gcp.project`
2. Environment variable `CULVERT_GCP_PROJECT`
3. ADC default via `com.google.cloud.ServiceOptions.getDefaultProjectId()`

On a Dataflow worker, ADC is always present and the metadata server provides the
project. In a test you set the system property. In a CI environment you set the
environment variable. The hook throws `IllegalStateException` with a diagnostic
message if none of the three yields a value — no silent failure, no metric loss
into the void with no explanation.

The `AutoCloseable` implementation closes the wrapped `MetricServiceClient`
(`CloudMonitoringMetricsHook.java:272`), mirroring the `DataCatalogLineageEmitter`
lifecycle contract. Resources transfer on construction; whoever builds the hook
is responsible for closing it, typically via try-with-resources in the stage
runner.

## `CulvertMdcPopulator` — structured-log correlation without ceremony

\index{CulvertMdcPopulator}\index{structured logging}The best observability
infrastructure is the kind pipeline engineers never have to think about. The
worst outcome is a `run_id` that engineers have to manually thread through every
logging call, and which is inevitably missing from 20% of log lines because
someone forgot.

`CulvertMdcPopulator`
(`CulvertMdcPopulator.java:44`) solves this with a static utility that writes
the three Culvert context fields into the SLF4J MDC for the duration of a stage
body, then clears them in a `finally` block:

```java
// CulvertMdcPopulator.java:77
public static <T> T withStageContext(
        String runId,
        String stageName,
        String pipelineId,
        Supplier<T> body) {

    MDC.put(RUN_ID_KEY, runId);
    MDC.put(STAGE_NAME_KEY, stageName);
    MDC.put(PIPELINE_ID_KEY, pipelineId);
    try {
        return body.get();
    } finally {
        MDC.remove(RUN_ID_KEY);
        MDC.remove(STAGE_NAME_KEY);
        MDC.remove(PIPELINE_ID_KEY);
    }
}
```

The three MDC keys are `run_id`, `stage_name`, and `pipeline_id`
(`CulvertMdcPopulator.java:47–53`). When Cloud Logging JSON output is active
via a Logback encoder configuration, every log line emitted inside the `finally`-
guarded body carries these three fields as top-level JSON keys. A Cloud Logging
filter of `jsonPayload.run_id="20260417T091400Z-7f3a"` then recovers every event
from a single run across every service it touched — without any manual MDC calls
in pipeline code.

There is a void variant (`CulvertMdcPopulator.java:112`) for stage bodies that
return nothing. Both variants guarantee the MDC is clean after the call, even
when the body throws. The class is a pure SLF4J concern — no GCP types, no Beam
types, no OTel dependency. It belongs in the GCP observability module only
because that is where the structured-logging story lives, but it would compile
against any Logback deployment.

The contrast with the v1 code I described in Chapter 11 of the original
manuscript is stark. The Python `LogContext` context manager did the same job
but as a separate object the pipeline code had to import. `CulvertMdcPopulator`
is invoked by the *framework* as part of stage dispatch — the pipeline author
does not see it. That is a better abstraction.

## `DataCatalogLineageEmitter` — lineage as Data Catalog tags

\index{DataCatalogLineageEmitter}\index{lineage}The lineage seam in Culvert is
`LineageEmitter`, a `@FunctionalInterface` in both Java and Python with one
method: `emit(LineageEvent)`. The GCP implementation writes lineage events as
Data Catalog tags on a configurable entry.

```java
// DataCatalogLineageEmitter.java:55
public final class DataCatalogLineageEmitter implements LineageEmitter, AutoCloseable {
    public void emit(LineageEvent event) {
        // flatten event sub-records to scalar fields
        // attach as a Tag to the configured Data Catalog entry
        client.createTag(request);
    }
}
```

Each `LineageEvent` becomes one `Tag` attached to the configured entry
(`DataCatalogLineageEmitter.java:95–115`). `LineageEvent` is a Java record with
four `Optional` sub-records: `source`, `pipeline`, `destination`, and `audit`
(`LineageEvent.java:23–27`). All four are optional because not every stage
produces every section — a streaming source emits no destination until the first
window closes. Construction uses a fluent builder: `LineageEvent.builder()` →
`.source(...)` → `.pipeline(...)` → `.destination(...)` → `.build()`
(`LineageEvent.java:36–54`). The `flatten()` helper in the emitter
(`DataCatalogLineageEmitter.java:137`) unpacks each sub-record to scalar strings
because Data Catalog tag fields are scalars. The `pipeline` sub-record carries
`run_id`, `pipeline_name`, `stage`, `started_at`, and `completed_at`
(`DataCatalogLineageEmitter.java:151–157`). A Data Catalog steward can find every
stage that touched a given table entry by querying its tags.

One design choice worth noting: the Javadoc
(`DataCatalogLineageEmitter.java:33–37`) is honest about why it targets Data
Catalog rather than the newer Cloud Data Lineage API:

> The newer Cloud Data Lineage API is not bundled in the GCP `libraries-bom`
> this module pins. To avoid an out-of-BOM version pin for a product still in
> transition, this Stage-2 implementation uses the stable v1 `DataCatalogClient`
> and stores lineage as tags. A dedicated `DataLineagePublisher` backed by the
> lineage API is deferred to sprint-5.

That is an honest engineering decision, not a limitation to hide. The lineage
information is in Data Catalog; the path to Cloud Data Lineage is clear; the
work is tracked. I would rather ship a working tag-based implementation today
than block on an API that is still moving.

The Python `LineageEmitter` Protocol
(`data-pipeline-core: contracts/lineage.py:18`) mirrors the Java interface with
`@runtime_checkable` structural subtyping. The contract's docstring names the
intended future default implementation (`OpenLineageEmitter`, targeting Marquez)
and the GCP implementation (`DataplexLineagePublisher`). Current status: only
`DataCatalogLineageEmitter` is built and held in v0.1.0.

## The run-ID thread

The four components I have described are only valuable as an ensemble. The
reason is `run_id`.

`CulvertMdcPopulator` writes `run_id` into the MDC so every log line carries
it. `CloudTraceObservabilityHook` carries `run_id` as a span attribute so Cloud
Trace groups spans by run. `CloudMonitoringMetricsHook` receives `run_id` via
the `StageMetrics` record and writes it as a metric label so Cloud Monitoring
can filter time-series to a single run. `DataCatalogLineageEmitter` flattens
`run_id` from the `LineagePipeline` sub-record into the Data Catalog tag so
lineage queries can join on the same identifier.

Put it together and you get what I described in the v1 manuscript as the only
definition of observability worth defending: a single click from a suspicious
Data Catalog tag through to the logs, the trace, the metrics, and the lineage
for that specific run. Not three dashboards — one thread.

The `WorkerSideHookResolutionTest`
(`WorkerSideHookResolutionTest.java:61`) proves this thread survives Beam
serialisation. A `DefaultRuntimeContext` is round-tripped through Java
object serialisation (simulating a Dataflow driver shipping the context to a
worker), and the post-deserialisation `stageMetrics()` call triggers
`AutoConfig.discover()` via `ServiceLoader`, which picks up
`CloudMonitoringMetricsHook` from the SPI registry and instantiates it via the
no-arg constructor — for real, not as a no-op. The test would have failed before
Sprint 12 because the no-arg constructor did not exist; without it,
`AutoConfig.discover()` silently skipped the class and the worker got a
no-op hook.

## The seam in use

A stage runner wires the observability ensemble in roughly this shape:

```java
try (CloudMonitoringMetricsHook metricsHook =
        new CloudMonitoringMetricsHook(monitoringClient, projectId);
     DataCatalogLineageEmitter lineageEmitter =
        new DataCatalogLineageEmitter(catalogClient, entryName, tagTemplate)) {

    CulvertMdcPopulator.withStageContext(runId, stageName, pipelineId, () -> {
        long startMs = System.currentTimeMillis();
        try (ObservabilityHook.Span span =
                observabilityHook.span("stage." + stageName)) {
            span.setAttribute("culvert.run_id", runId);
            // ... stage logic ...
            long rows = processRecords();
            long latencyMs = System.currentTimeMillis() - startMs;

            metricsHook.recordStageMetrics(
                new StageMetrics(pipelineId, runId, stageName,
                    rows, latencyMs, 0L));

            lineageEmitter.emit(LineageEvent.builder()
                .source(source).pipeline(pipelineMeta).destination(dest)
                .build());
        }
    });
}
```

The pattern is mechanical, which means it can be generated. The Beam integration
work (T12.3) is where the try-with-resources and the `CulvertMdcPopulator`
wrapping get encapsulated into a reusable DoFn base so stage authors only
override `processElement`. This chapter describes the seam; Chapter 9 covers the
Beam wiring that hides it.

## Honest status

Culvert v0.1.0 is built and held. Nothing is published to Maven Central or PyPI
yet. The observability module specifically:

- `CloudTraceObservabilityHook` — built, tested, ServiceLoader-registered.
  Gauge implementation has the OTel 1.38 workaround noted above; fix is
  straightforward when the SDK bumps.
- `CloudMonitoringMetricsHook` — built, tested, ServiceLoader-registered.
  Verified end-to-end by `WorkerSideHookResolutionTest`.
- `CulvertMdcPopulator` — built, tested, no external dependencies.
- `DataCatalogLineageEmitter` — built, tested. Uses Data Catalog tags (stable);
  migration to Cloud Data Lineage API deferred and tracked.
- Python `ObservabilityHook` and `LineageEmitter` protocols — defined in
  `data-pipeline-core` v0.1.0, with the GCP adapter implementations now built in
  `data-pipeline-gcp-observability` (Cloud Trace hook, Cloud Monitoring metrics
  hook, Data Catalog lineage emitter), discoverable via the
  `data_pipeline_core.adapters` entry-points. The Java adapters remain the
  primary path for Beam-on-Dataflow workloads, where the hooks run inside the
  `DoFn`.

The coordinated Maven Central + PyPI `culvert` release is future work, gated on
the full adapter set being verified against real GCP projects in both languages.

\begin{takeaways}
\textbf{Key takeaways}
\begin{itemize}
  \item Culvert splits observability across two contracts: \texttt{ObservabilityHook} (general-purpose metrics/logs/spans) and \texttt{StageMetricsHook} (typed, three-metric, three-label contract for per-stage reporting). The narrowness of the second contract is deliberate — it prevents label drift and enables type-safe constructors.
  \item \texttt{CloudTraceObservabilityHook} bridges the Culvert surface to OpenTelemetry and gracefully degrades: if no OTel SDK is wired, the no-arg constructor wraps the GlobalOpenTelemetry no-op and every call is a silent discard. The pipeline runs unmodified; it just does not produce traces.
  \item \texttt{CulvertMdcPopulator} writes \texttt{run\_id}, \texttt{stage\_name}, and \texttt{pipeline\_id} into the SLF4J MDC for the duration of a stage body, then clears them in a \texttt{finally} block. Pipeline code never has to pass context to a logger manually; Cloud Logging sees it on every line.
  \item \texttt{DataCatalogLineageEmitter} stores lineage as Data Catalog tags rather than the newer Cloud Data Lineage API — an honest trade-off taken to avoid an out-of-BOM version pin. Migration path is tracked; the current implementation is functional and stable.
  \item The \texttt{run\_id} is the thread that ties every log line, metric point, trace span, and lineage tag to the same pipeline run. Three dashboards without a shared identity are noise. One identifier that threads thirty artefacts together is observability.
\end{itemize}
\end{takeaways}

\newpage

# Chapter 13 — Cost and FinOps

\index{FinOps}

A pipeline that nobody can afford to run is not a product. It is a proof of concept with a billing alarm attached.

I say that because I have watched it happen — not once, not twice. The pattern is consistent enough that I now consider it a distinct class of pipeline failure: technically green, financially untenable. The Dataflow job returns `SUCCESS`. The BigQuery table is populated. The audit trail is clean. And then the finance team sends an email on the fifteenth of the month and the engineering lead learns, for the first time, that the entity they put into production last quarter is spending more per day than the product it feeds earns per week.

This happens when cost is an afterthought. Culvert treats it as a first-class concern — not because "FinOps" is a fashionable acronym but because I built the framework after living through the consequences of the alternative. Everything in this chapter is earned the hard way.

## Cost as a metric, not an invoice line

The first thing Culvert does differently is treat cost the same way it treats any other operational metric: measured per run, attributed per entity, stored in a queryable table, and surfaced before the pipeline runs if it is going to be expensive.

The `FinOpsSink` contract is the seam that makes this possible.

```java
// data-pipeline-libraries-java/data-pipeline-core-java/src/main/java/
//   com/enrichmeai/culvert/contracts/FinOpsSink.java:17–27
@FunctionalInterface
public interface FinOpsSink {

    /**
     * Record cost metrics with attribution tags.
     *
     * Implementations may batch internally; the framework calls this once
     * per cost-incurring operation (a BigQuery query, a GCS upload, a Pub/Sub
     * publish) and the sink decides when to flush.
     */
    void record(CostMetrics metrics, FinOpsTag tags);
}
```

\index{FinOpsSink}

One method. The cloud-specific cost tracker calls it once per operation; the sink decides what to do with the record. The `BigQueryFinOpsSink` streams it into a `cost_metrics` table. A test double captures it in memory. A future Athena sink would write to S3. The contract does not care.

There is a design decision hidden in this signature that I want to explain, because it took a failed integration test to understand it properly. The tags — `FinOpsTag` — are passed explicitly to `record()`. They are not read from a runtime context or inferred from ambient state.

The reason is attribution loss. Cost emissions are infrequent: one call per BigQuery query, one per GCS upload batch, one per Pub/Sub publish. But lossy attribution is the most common bug in cost tracking systems. Ambient context can be overwritten. Thread locals can bleed. Reactor context can be dropped across async boundaries. Explicit tags make the data flow visible at every call site — you can read `tracker.trackJob(job, runId, tag)` and see exactly what attribution is being recorded. If it is wrong, the mistake is on that line, not somewhere in a context propagation chain three calls up. The comment in the source is direct about this: "Cost emissions are infrequent and lossy attribution is the most common bug; explicit tags make the data flow visible" (`data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/contracts/finops.py:10–12`).

## `CostMetrics` and `FinOpsTag`: what travels through the seam

\index{CostMetrics}\index{FinOpsTag}

`CostMetrics` is a record — immutable, value-typed, with all numeric fields defaulting to zero. The fields cover what every cloud charges for: bytes scanned (BigQuery queries), bytes written (loads, GCS uploads, Pub/Sub), bytes stored (GCS object lifetime), message counts (Pub/Sub), slot-milliseconds (BigQuery flat-rate), and a generic `computeUnits` field for warehouses that bill differently.

```java
// data-pipeline-libraries-java/data-pipeline-core-java/src/main/java/
//   com/enrichmeai/culvert/finops/CostMetrics.java:32–52
public record CostMetrics(
        String runId,
        double estimatedCostUsd,
        long billedBytesScanned,
        long billedBytesWritten,
        long billedBytesStored,
        long billedMessagesCount,
        long slotMillis,
        double computeUnits,
        Map<String, String> labels,
        Instant timestamp) { ... }
```

The zero-default pattern matters. A GCS upload tracker does not know the slot-milliseconds; a Pub/Sub tracker does not know the bytes stored. Rather than inventing a hierarchy of subtypes — `BigQueryCostMetrics`, `GcsCostMetrics` — the same record carries whatever the cloud service measured and leaves the rest at zero. The record that travels from `BigQueryCostTracker` to `BigQueryFinOpsSink` happens to have `billedBytesScanned` and `slotMillis` populated; the one from `GcsCostTracker` has `billedBytesStored`. Downstream analytics are straightforward `SUM` queries grouped by field.

The Python mirror is a dataclass:

```python
# data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/
#   finops_api/models.py:22–40
@dataclass
class CostMetrics:
    run_id: str
    estimated_cost_usd: float = 0.0
    billed_bytes_scanned: int = 0
    billed_bytes_written: int = 0
    billed_bytes_stored: int = 0
    billed_messages_count: int = 0
    slot_millis: int = 0
    compute_units: float = 0.0
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=_utc_now)
```

Identical fields, identical semantics, different language. This is the polyglot contract pattern from Chapter 6 applied to cost data: one conceptual type, two implementations, one set of analytics queries over the result.

`FinOpsTag` is the attribution metadata that travels alongside every `CostMetrics` record:

```java
// data-pipeline-libraries-java/data-pipeline-core-java/src/main/java/
//   com/enrichmeai/culvert/finops/FinOpsTag.java:24–49
public record FinOpsTag(
        String system,
        String environment,
        String costCenter,
        String owner,
        String runId,
        Map<String, String> extra) { ... }
```

Five required fields — system, environment, cost centre, owner, run ID — and an `extra` map for anything else the team needs (business unit, feature flag, customer tier). The Python mirror is a frozen dataclass in `data-pipeline-core/src/data_pipeline_core/finops_api/labels.py:17–30`. The name is deliberate: it used to be `FinOpsLabels` (a GCP-specific term) and was renamed `FinOpsTag` because AWS calls them tags, Azure calls them tags, and cloud-neutral vocabulary matters if you want adapters to compose cleanly. That rename echoes exactly the framework rename story in Chapter 4.

## The three service trackers

\index{BigQueryCostTracker}\index{GcsCostTracker}\index{PubSubCostTracker}

Culvert ships three service-specific cost trackers for GCP. Each lives in its cloud-adapter module, holds a reference to the `FinOpsSink`, and knows how to translate raw cloud-API statistics into a `CostMetrics` record.

### BigQuery: bytes billed and slot-milliseconds

`BigQueryCostTracker` (`data-pipeline-libraries-java/data-pipeline-gcp-bigquery-java/src/main/java/com/enrichmeai/culvert/gcp/bigquery/BigQueryCostTracker.java`) reads `JobStatistics` from a completed BigQuery `Job` and calls the sink.

The cost formula for query jobs:

```
estimatedCostUsd = billedBytesScanned / BYTES_PER_TIB * QUERY_COST_USD_PER_TIB
```

The constants are not magic numbers:

```java
// BigQueryCostTracker.java:81
public static final long BYTES_PER_TIB = 1_099_511_627_776L; // 2^40

// BigQueryCostTracker.java:90
public static final double QUERY_COST_USD_PER_TIB = 5.00;
```

\index{BigQuery!pricing}

`BYTES_PER_TIB` is exactly 2^40 — not 10^12. This is the binary definition of tebibyte that BigQuery's pricing page uses. If you use one trillion instead you undercount by roughly ten per cent. That is a ten per cent undercount on your most expensive queries. At scale, that is real money going unaccounted for. The constant is named and documented for precisely this reason: the wrong answer is not dramatically wrong, it is plausibly wrong, which is worse.

`QUERY_COST_USD_PER_TIB` is $5.00 per tebibyte scanned, the 2025 BigQuery on-demand rate. The formula runs at line 325:

```java
// BigQueryCostTracker.java:321–326
private static double bytesToUsd(long bytes, double costPerTib) {
    if (bytes <= 0L) {
        return 0.0;
    }
    return (double) bytes / (double) BYTES_PER_TIB * costPerTib;
}
```

For load jobs, `BigQueryCostTracker` uses a placeholder rate of `LOAD_COST_USD_PER_TIB = 0.01` (`BigQueryCostTracker.java:103`). BigQuery batch loads are actually free to ingest; the constant represents GCS-egress-equivalent accounting for teams that want to attribute the cost of moving data. The Javadoc says so explicitly, and teams may set it to zero.

### GCS: bytes written and storage class

`GcsCostTracker` (`data-pipeline-libraries-java/data-pipeline-gcp-gcs-java/src/main/java/com/enrichmeai/culvert/gcp/gcs/GcsCostTracker.java`) tracks two operation types: uploads and storage-class attribution.

The storage formula:

```
estimatedCostUsd = bytesStored / BYTES_PER_GIB * rateForClass
```

Storage is priced in **gibibytes**, not tebibytes, so the denominator shifts:

```java
// GcsCostTracker.java:77
public static final long BYTES_PER_GIB = 1_073_741_824L; // 2^30
```

The per-class monthly rates (US multi-region, 2025):

```java
// GcsCostTracker.java:99,108,117,126
public static final double STANDARD_STORAGE_USD_PER_GIB  = 0.020;  // $0.020/GiB-month
public static final double NEARLINE_STORAGE_USD_PER_GIB  = 0.010;  // $0.010/GiB-month
public static final double COLDLINE_STORAGE_USD_PER_GIB  = 0.004;  // $0.004/GiB-month
public static final double ARCHIVE_STORAGE_USD_PER_GIB   = 0.0012; // $0.0012/GiB-month
```

\index{GCS!storage pricing}

The formula at line 244–248:

```java
// GcsCostTracker.java:244–248
private static double bytesToUsd(long bytes, double ratePerGib) {
    if (bytes <= 0L) {
        return 0.0;
    }
    return (double) bytes / (double) BYTES_PER_GIB * ratePerGib;
}
```

The upload tracker uses `WRITE_COST_USD_PER_GIB = 0.01` (`GcsCostTracker.java:90`) — another accounting placeholder, since GCS charges per-10,000 Class A operations rather than per byte. Teams that do not need per-upload attribution can zero it out.

An unknown storage class falls back to the Standard rate with a `WARN` log rather than throwing. Cost tracking should never crash the pipeline.

### Pub/Sub: throughput bytes

`PubSubCostTracker` (`data-pipeline-libraries-java/data-pipeline-gcp-pubsub-java/src/main/java/com/enrichmeai/culvert/gcp/pubsub/PubSubCostTracker.java`) records both the message count and the throughput bytes for publish and subscribe operations.

I want to dwell on this one for a moment, because it contains the clearest example of why the outline for this book flags pricing as a danger zone. The original ticket for the Pub/Sub tracker — issue #70 — described the cost as "$0.04/MiB". That figure is approximately one thousand times the actual rate. The Javadoc notes this explicitly:

```java
// PubSubCostTracker.java:76–79
// Note on issue #70 paraphrase: the ticket text mentioned
// "$0.04/MiB" which is approximately 1000× the actual per-TiB rate
// ($40/TiB ≈ $0.000038/MiB). This constant uses the correct per-TiB
// billing unit from the GCP pricing page.
```

\index{Pub/Sub!pricing}

The correct constants:

```java
// PubSubCostTracker.java:65
public static final long BYTES_PER_TIB = 1_099_511_627_776L; // 2^40

// PubSubCostTracker.java:81
public static final double THROUGHPUT_COST_USD_PER_TIB = 40.00;
```

The formula at lines 182–186:

```java
// PubSubCostTracker.java:182–186
private static double bytesToUsd(long bytes) {
    if (bytes <= 0L) {
        return 0.0;
    }
    return (double) bytes / (double) BYTES_PER_TIB * THROUGHPUT_COST_USD_PER_TIB;
}
```

Pub/Sub charges $40 per tebibyte of message throughput, with the first 10 GiB per month free. The tracker records gross cost — no free-tier deduction — so per-run attribution is consistent regardless of how far the monthly free tier has been consumed. The `billedMessagesCount` field is populated for attribution purposes but does not contribute to the USD estimate, since Pub/Sub bills on throughput bytes, not per-message.

Both the message count and total bytes figure are recorded for every operation. A pipeline that publishes ten thousand tiny messages and one that publishes ten large ones might have identical throughput cost but very different operational profiles; keeping both numbers means the analytics table can surface either cut.

## The dry-run pre-flight: enforcement before the spend

Here is where cost tracking becomes cost *control*.

The `BigQueryCostTracker` has an `estimateDryRun` method that submits a BigQuery dry-run job — the query is validated and estimated without actually executing — and returns a `CostMetrics` with only `estimatedCostUsd` and `billedBytesScanned` populated. All other fields are zero; this is a pre-flight estimate, not an execution record.

```java
// BigQueryCostTracker.java:193–234
public CostMetrics estimateDryRun(QueryJobConfiguration config, String runId) {
    QueryJobConfiguration dryRunConfig = config.toBuilder()
            .setDryRun(true)
            .build();
    Job dryRunJob = client.create(JobInfo.of(dryRunConfig));
    Job completedJob = dryRunJob.waitFor();
    // ... null-safety + fallback to getTotalBytesProcessed() if billed is null
    long bytesScanned = resolveDryRunBytes(qs, runId);
    double costUsd = bytesToUsd(bytesScanned, QUERY_COST_USD_PER_TIB);
    return CostMetrics.builder(runId)
            .billedBytesScanned(bytesScanned)
            .estimatedCostUsd(costUsd)
            .build();
}
```

A quick note on the dry-run contract: BigQuery dry-run jobs are designed to populate `getTotalBytesBilled()`, but in practice the field can be null or zero on some responses — because no billing event occurs on a job that never executes. The tracker falls back to `getTotalBytesProcessed()` and logs a `WARN` if that happens (`BigQueryCostTracker.java:303–317`). This is flagged in the Javadoc as a runtime guarantee to verify against the emulator integration test (`BigQueryCostTrackerIT`). Honest status: the fallback is there; whether you hit it depends on the BigQuery version responding to your project.

That estimated `CostMetrics` is the input to `BudgetGovernancePolicy`.

## Budget governance: `BudgetGovernancePolicy` and `BudgetViolationMode`

\index{BudgetGovernancePolicy}\index{BudgetViolationMode}\index{BudgetExceededException}

`BudgetGovernancePolicy` (`data-pipeline-libraries-java/data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/finops/BudgetGovernancePolicy.java`) is the enforcement gate. It holds a cost ceiling in USD and a `BudgetViolationMode` — either `BLOCK` or `WARN` — and exposes one method:

```java
// BudgetGovernancePolicy.java:116
public void checkBudget(CostMetrics projected, String runId) throws BudgetExceededException
```

The logic is strict-greater-than: if `projected.estimatedCostUsd() > ceilingUsd`, the violation triggers. If cost equals the ceiling exactly, the run is allowed. The boundary test in the unit suite makes this explicit:

```java
// BudgetGovernancePolicyTest.java:81–89
@Test
void block_mode_does_not_throw_when_cost_equals_ceiling_boundary() {
    // Boundary: cost == ceiling is ALLOWED (strict > semantics).
    BudgetGovernancePolicy policy =
            new BudgetGovernancePolicy(CEILING_USD, BudgetViolationMode.BLOCK);
    CostMetrics exactCeiling = metricsWithCost(CEILING_USD);
    assertThatCode(() -> policy.checkBudget(exactCeiling, RUN_ID))
            .doesNotThrowAnyException();
}
```

In `BLOCK` mode, a violation throws `BudgetExceededException`. The message is human-readable — `"Budget ceiling exceeded for run 'run-id': projected cost $31.2500 USD > ceiling $25.0000 USD"` — so it surfaces cleanly in a log or alert without additional formatting. The typed accessors (`getRunId()`, `getProjectedCostUsd()`, `getCeilingUsd()`) are there for programmatic handling (`BudgetExceededException.java:35–57`).

In `WARN` mode, the policy logs at `WARNING` level via `java.util.logging` and returns normally. The run continues.

The wiring into `DefaultRuntimeContext` looks like this:

```java
// BudgetGovernancePolicy.java:53–63 (Javadoc example)
BudgetGovernancePolicy budget =
        new BudgetGovernancePolicy(50.0, BudgetViolationMode.BLOCK);
RuntimeContext ctx = DefaultRuntimeContext.builder("run-1", "prod")
        .register(GovernancePolicy.class, budget)
        .build();

// Pre-flight check before submitting the job:
CostMetrics estimate = costTracker.estimateDryRun(queryConfig, ctx.runId());
budget.checkBudget(estimate, ctx.runId()); // throws BudgetExceededException if over ceiling
```

The flow is: `estimateDryRun` → `CostMetrics` → `checkBudget` → proceed or throw. If it throws, the BigQuery job is never submitted. The spend never happens. That is the difference between observability and control.

`BudgetGovernancePolicy` implements `GovernancePolicy` (`contracts/GovernancePolicy`) with no-op pass-throughs for `classify`, `maskingFor`, and `retentionFor` (`BudgetGovernancePolicy.java:162–182`). Cost enforcement and data governance are composable concerns. A pipeline that needs both registers a real `GovernancePolicy` delegate for classification and masking, and wraps it with `BudgetGovernancePolicy` for budget enforcement.

The policy is intentionally cloud-neutral. It imports only `java.*` and `com.enrichmeai.culvert.*` — no `com.google.cloud.*`, no `org.apache.beam.*`. The unit test suite asserts this invariant by grepping the source file for cloud imports (`BudgetGovernancePolicyTest.java:265–283`). `BudgetGovernancePolicy` could enforce budgets on Redshift queries, Azure Synapse runs, or any source that produces a `CostMetrics` record. The enforcement logic does not know or care what cloud generated the number.

The Python mirror in `data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/finops_api/budget.py` is a direct port: `BudgetViolationMode` as a `str, Enum` with `BLOCK = "block"` and `WARN = "warn"`, `BudgetExceededException` with the same typed properties, and `BudgetGovernancePolicy.check_budget()` with the same strict-greater-than semantics (`budget.py:29–209`).

## The sink: `BigQueryFinOpsSink` and the `cost_metrics` table

\index{BigQueryFinOpsSink}

`BigQueryFinOpsSink` (`data-pipeline-libraries-java/data-pipeline-gcp-bigquery-java/src/main/java/com/enrichmeai/culvert/gcp/bigquery/BigQueryFinOpsSink.java`) is the production implementation of `FinOpsSink`. It streams a row into a BigQuery table for every `record()` call, using `insertAll` for sub-second queryability.

The table name follows the convention `cost_metrics` (`BigQueryFinOpsSink.java:60`). Every field from both `CostMetrics` and `FinOpsTag` is flattened into columns. The `labels` and `extra` maps are stored as `RECORD<key STRING, value STRING>` arrays — BigQuery's only stable representation for arbitrary map data without a schema change per row. The wire format is built in `toRow()` (`BigQueryFinOpsSink.java:113–141`).

One operational consideration: streaming inserts land in BigQuery's streaming buffer. Rows are queryable within seconds but not immediately available to `COPY` or `EXPORT` jobs — the buffer flushes to managed storage on BigQuery's own schedule, usually within 90 minutes. For most cost analytics this is acceptable. For high-volume cost emission, a load-job-based variant is a future option; the `FinOpsSink` contract makes swapping it in a single constructor call.

Partial failures matter here. `InsertAllResponse` can succeed at the HTTP level while reporting per-row failures. `BigQueryFinOpsSink` treats any non-empty `getInsertErrors()` as a hard failure and throws `FinOpsInsertException` (`BigQueryFinOpsSink.java:101–104`). Silently dropping cost rows would defeat the purpose of having an audit trail. The failure is loud by design.

## Querying cost: `CostAnalysisQueries`

\index{CostAnalysisQueries}

`CostAnalysisQueries` (`data-pipeline-libraries-java/data-pipeline-gcp-bigquery-java/src/main/java/com/enrichmeai/culvert/gcp/bigquery/CostAnalysisQueries.java`) is a utility that loads named SQL blocks from a classpath resource (`sql/cost_analysis.sql`). Four queries ship:

- `cost_by_run` — total estimated USD and slot-milliseconds grouped by `run_id`, ordered by cost descending.
- `cost_by_stage` — total estimated USD grouped by the `stage` label key (UNNESTing the labels array).
- `top_expensive_runs_7d` — the ten most expensive `run_id`s in the past seven days.
- `budget_breach_log` — all rows where `estimated_cost_usd > ?` (positional parameter), ordered by timestamp descending.

The query that answers "which entity is my most expensive?" is two lines of SQL:

```sql
-- cost_analysis.sql (top_expensive_runs_7d, adapted for entity label)
SELECT run_id, SUM(estimated_cost_usd) AS total_estimated_cost_usd, ...
FROM cost_metrics
WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
GROUP BY run_id ORDER BY total_estimated_cost_usd DESC LIMIT 10;
```

Without the `cost_metrics` table and the `run_id`-keyed rows that flow into it, that question requires a week of billing-export archaeology. With it, the answer is a weekend SQL query. That shift — from archaeology to query — is the point of the FinOps layer.

## A FinOps reality check

\index{FinOps!practices}

I will be direct here, because the framework ships first-class cost tracking and I want to be clear about what that gets you and what it does not.

Cost tracking is not cost control. The framework makes the data trivial to surface; the team has to choose to look at it on a cadence that catches problems while they are still small.

**Things that work.** Per-entity `FinOpsTag` on every Dataflow job, BigQuery query, and Pub/Sub batch, with a weekly query over `cost_metrics` that surfaces the top ten entities by daily spend. A fifteen-minute cost-trend review with the engineering lead and the product owner, once a week, looking at the deltas. Budget alerts at 50%, 75%, 90%, and 100% of monthly target — and the 100% alert must page the on-call, not just email a distribution list. GCS lifecycle rules that move landing bucket objects to Coldline after 90 days and Archive after a year: do this once at provisioning, never think about it again. Cloud Composer is the single most expensive resource in the stack — roughly £250–400/month for `ENVIRONMENT_SIZE_SMALL` — and the `docs/FINOPS_STRATEGY.md` policy is correct: Composer is disabled by default (`enable_composer = false` in Terraform, `deploy_composer = false` in the deploy workflow) and enabled only via explicit manual dispatch. Standing rule: any new Dataflow job runs with `--max-workers` set; jobs that want more get reviewed.

**Things that do not work.** Daily cost dashboards that nobody reads. Slack channels that fire on every budget alert until the channel is muted. Monthly cost optimisation reviews that get cancelled whenever the team is under pressure — which is always. Reactive optimisation after a finance complaint; by then the budget is spent and the muscle memory for preventing it next time is not built.

The `BudgetViolationMode.WARN` setting is development mode. In staging and production, use `BLOCK`. The reason is simple: if you allow the run to proceed when it is over budget, the cost ceiling is advisory rather than enforced, and advisory ceilings accumulate exceptions until they stop meaning anything. BLOCK mode means someone has to consciously raise the ceiling rather than quietly letting overruns through. That conversation is the one you want happening before the finance email arrives.

## What the polyglot mirror shows

One of the more interesting things about implementing both Java and Python cost types is what the mirroring reveals about the abstraction.

The Java `FinOpsTag` Javadoc says: "Replaces the older `FinOpsLabels` class on the Python side; the rename signals the universal vocabulary (AWS tags, Azure tags, GCP labels all map cleanly)" (`FinOpsTag.java:14–16`). The Python `labels.py` opens with the same rationale: "`labels` is a GCP-specific term; `tags` is the universal vocabulary" (`labels.py:5–7`). The rename happened in both languages, from the same motivation, to the same result.

That consistency is not coincidental. It is the outcome of designing the contract first and the implementation second. When you have a language-neutral name (`FinOpsTag`, `CostMetrics`, `BudgetGovernancePolicy`) that both languages have to implement, you cannot allow GCP terminology to leak into the core type — it would break the Java mirror immediately. The discipline of maintaining the mirror is also the discipline of keeping the contract clean.

The GCP predecessor in `gcp-pipeline-libraries/gcp-pipeline-core/src/gcp_pipeline_core/finops/tracker.py` used `BQ_COST_PER_TIB = 6.25` and wrote to a `finops_usage` table. Culvert 0.1.0 uses `QUERY_COST_USD_PER_TIB = 5.00` and the `cost_metrics` table. The rate difference reflects the updated 2025 GCP pricing; the table rename reflects the contract-first design. Both are correct for their context.

\begin{takeaways}
\textbf{Key takeaways}
\begin{itemize}
  \item The \texttt{FinOpsSink} contract is a single-method seam: \texttt{record(CostMetrics, FinOpsTag)}. Cloud-specific cost trackers (\texttt{BigQueryCostTracker}, \texttt{GcsCostTracker}, \texttt{PubSubCostTracker}) call it once per cost-incurring operation; the sink handles persistence. Attribution tags (\texttt{FinOpsTag}) are passed explicitly — not inferred from ambient context — because lossy attribution is the most common bug in cost tracking.
  \item Pricing constants are not magic numbers. BigQuery on-demand: $5.00/TiB where TiB = 2\textsuperscript{40} = \texttt{1\_099\_511\_627\_776}\ bytes (\texttt{BigQueryCostTracker.java:81,90}). GCS storage: per-GiB-month where GiB = 2\textsuperscript{30}; Standard \$0.020, Nearline \$0.010, Coldline \$0.004, Archive \$0.0012. Pub/Sub throughput: \$40.00/TiB. The Pub/Sub ticket that described the rate as \$0.04/MiB was off by 1000×; the code documents the correction.
  \item \texttt{BudgetGovernancePolicy} enforces a cost ceiling before the pipeline runs. \texttt{estimateDryRun()} yields a \texttt{CostMetrics} estimate; \texttt{checkBudget()} either throws \texttt{BudgetExceededException} (BLOCK mode) or logs a WARNING (WARN mode). Cost equals ceiling is allowed — the check is strict-greater-than. The policy is cloud-neutral: no \texttt{com.google.cloud.*} imports.
  \item \texttt{CostAnalysisQueries} ships four named SQL blocks — \texttt{cost\_by\_run}, \texttt{cost\_by\_stage}, \texttt{top\_expensive\_runs\_7d}, \texttt{budget\_breach\_log} — that answer the operational questions in seconds rather than a week of billing-export archaeology.
  \item Cost discipline is a habit, not a quarterly initiative. Use BLOCK mode in production. Set \texttt{--max-workers} on every Dataflow job. Run a fifteen-minute weekly cost review. Deploy Composer only on explicit dispatch. The framework makes the data available; the team has to choose to use it.
\end{itemize}
\end{takeaways}

\newpage

# Chapter 14 — Governance, Masking, and Data Quality

There is a conversation I find myself having with new teams at a depressing regularity.
It usually starts a few months after they ship their first pipeline. The pipeline
works — data is flowing, the dashboard is live, the stakeholders are happy. Then
someone from the compliance function turns up and asks three questions: "Which fields
contain personal data?", "Who can see the unmasked values?", and "How do we know the
data is actually correct before it hits the downstream system?" The engineering team
looks at one another. They can answer each question with twenty minutes of
archaeology — grep the source, trace the schema, find the IAM bindings — but they
cannot answer them in one sentence. That is the governance gap.

Culvert's governance seam exists to close that gap at the framework level, not as an
afterthought bolted on once the regulator comes knocking. This chapter walks through
the concrete implementation: the `GovernancePolicy` Protocol\index{GovernancePolicy}
that every adapter can interrogate, the `PiiMaskingGovernancePolicy`\index{PiiMaskingGovernancePolicy}
that is the only concrete shipped today, the `Masker`\index{Masker} with its five strategies,
the `DataClassification` taxonomy, the `MaskingPolicy` and `RetentionPolicy` value
types, and the data-quality layer built on top of it all. I will say plainly where
the framework stops and where the layer above — Dataplex, Cloud DLP, policy tags —
begins. Conflating the two is a reliable way to write a chapter that sounds good and
ships broken pipelines.


## The `GovernancePolicy` seam

Everything in Culvert's governance story hangs off a single contract. The
`GovernancePolicy` Protocol\index{GovernancePolicy!Protocol} (Python) and interface
(Java) defines three methods:

```python
# data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/contracts/governance.py:22–46

@runtime_checkable
class GovernancePolicy(Protocol):

    def classify(self, field: str, table: str) -> DataClassification:
        ...

    def masking_for(self, field: str, table: str) -> Optional[MaskingPolicy]:
        ...

    def retention_for(self, table: str) -> Optional[RetentionPolicy]:
        ...
```

Three questions, three methods. `classify` returns the sensitivity tier for a given
field in a given table. `masking_for` returns the policy that governs how that field
should be masked, or `None` if no masking applies. `retention_for` returns how long a
table's rows should be kept before they must be deleted or archived, or `None` if the
table lives indefinitely.

The contract is cloud-neutral by design. The docstring says what I mean:
implementations "may consult Dataplex (GCP), Glue Data Catalog (AWS), Purview
(Azure), or a static YAML file shipped with the project." A pipeline author working
against this contract does not know — and should not need to know — whether their
classification decision came from a Dataplex tag lookup or a YAML file loaded at
start-up. The adapter seam is the whole point. The framework ships one concrete
implementation today: `PiiMaskingGovernancePolicy`.


## `DataClassification`: the four tiers\index{DataClassification}

Before talking about how fields are masked, I need to be clear about how they are
classified. Culvert's `DataClassification` enum uses the same four-tier model that
Dataplex, AWS Macie, and Azure Purview all converge on:

```python
# data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/governance_api/classification.py:12–18

class DataClassification(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"   # PII, PHI, financial — strongest controls
```

In practice, `PiiMaskingGovernancePolicy` — the only concrete shipped today — only
ever returns `RESTRICTED` (for matched PII fields) or `INTERNAL` (for everything
else). The `CONFIDENTIAL` tier and finer-grained classification are reserved for
richer implementations. I mention this because I have seen teams read the enum,
assume all four tiers are plumbed in, and design access policies around `CONFIDENTIAL`
that the framework never actually emits. It doesn't, yet. One tier for PII, one for
everything else: that is the honest current state.\index{DataClassification!RESTRICTED}


## `MaskingPolicy` and `RetentionPolicy`: the value objects\index{MaskingPolicy}\index{RetentionPolicy}

The two policy dataclasses are in `policies.py`:

```python
# data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/governance_api/policies.py:15–56

class MaskingStrategy(str, Enum):
    FULL     = "full"     # entire value replaced with constant
    PARTIAL  = "partial"  # most chars replaced, last 4 kept
    REDACTED = "redacted" # value removed, sentinel returned
    HASH     = "hash"     # deterministic hash
    NONE     = "none"     # explicitly no masking (overrides defaults)

@dataclass(frozen=True)
class MaskingPolicy:
    strategy:    MaskingStrategy
    replacement: str = "*"
    salt:        str = ""

@dataclass(frozen=True)
class RetentionPolicy:
    retention_days: int
    legal_hold:     bool = False
    purpose:        Optional[str] = None
```

`MaskingPolicy` is deliberately tiny. Three fields: what strategy, what replacement
string (used by `FULL` and `REDACTED`; the mask character for `PARTIAL`; the salt for
`HASH`), and the salt itself. `RetentionPolicy` is equally spare: how many days, a
`legal_hold` flag that overrides the window entirely, and a free-text `purpose` that
appears in deletion audit records.

The `legal_hold` flag deserves a sentence. When it is `True`, no deletion is
permitted regardless of the age of the rows. This exists because financial regulators
have a habit of issuing hold notices mid-investigation. When that happens, you want
the framework to have a single boolean you can flip rather than a custom deletion
override scattered across several jobs.


## `MaskingStrategy`: five values, one gap\index{MaskingStrategy}

v1 of this framework — the GCP-native predecessor — shipped exactly one masking
strategy: hashing. Not because we did not know the others existed, but because for
the specific use case we were solving (regulated mainframe-to-BigQuery pipelines with
strict need-to-know) irreversible, deterministic hashing was exactly right. Analysts
can still `GROUP BY` and `COUNT(DISTINCT)` over a hashed PII column. They cannot
re-identify the individual. That trade-off was the correct one for that context.

Culvert ships four actionable strategies and one explicit no-op. Let me go through
them plainly.

**`NONE`** — the value is returned unchanged. This is the explicit override when a
field name pattern or prefix would otherwise catch a column that is not actually PII.
You declare it deliberately so the intent is auditable, not implicit.\index{MaskingStrategy!NONE}

**`HASH`** — a deterministic SHA-256 hex digest of the string representation,
prefixed with a salt. The constant default salt is `"culvert-pii-salt"`, mirrored
between both languages (Python `masker.py:36`; Java `Masker.java:41`). Null
passthrough applies: a `None` value is returned as `None` without fabrication. Two
identical input values produce identical hashes, which preserves `GROUP BY` and
`DISTINCT` semantics at the cost of reversibility. That cost is usually a
feature.\index{MaskingStrategy!HASH}

**`FULL`** — the entire value is replaced with `policy.replacement` (default `"*"`).
No part of the original value survives. Use this when the column should not appear in
the consumer view at all but you want a sentinel rather than a `NULL`.\index{MaskingStrategy!FULL}

**`REDACTED`** — identical to `FULL` in implementation; the `Masker` treats both the
same way (Python `masker.py:67–68`; Java `Masker.java:59–60`). The distinction is
semantic: `FULL` signals "replaced wholesale", `REDACTED` signals "regulatory
removal". Downstream systems that inspect the strategy enum can branch on it; the
masking engine itself does not.

**`PARTIAL`** — all characters except the last four are replaced with the mask
character. "Show me the last four of the card number" is the request every fraud
team makes; this is the answer. If the value has four or fewer characters, every
character is replaced. Non-string values are `str()`-cast before the operation.\index{MaskingStrategy!PARTIAL}

The strategy that is *not* yet shipped is **tokenisation** — reversible via a secure
vault, with format-preserving variants for card numbers and the like. This is the gap
the fraud investigation team will find. The `MaskingStrategy` enum does not have a
`TOKEN` value. If your organisation has a customer-services population that needs to
look up real records, or a fraud team that runs investigations from the FDP layer, you
will need to add tokenisation and wire it to a KMS-backed service. The enum and the
`Masker` are the right extension point; the Protocol boundary keeps that addition
contained to a single implementation class and one new enum value.\index{tokenisation}


## The `Masker`: applied strategy\index{Masker}

The `Masker` is a pure-Python, cloud-neutral utility function. No GCP SDK. No Cloud
DLP. No Dataplex. It does not inspect cell values for PII patterns — that is the job
of `PiiMaskingGovernancePolicy`. `Masker` only *applies* a strategy to a value that
someone upstream has already decided should be masked.

```python
# data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/governance_api/masker.py:39–75

def mask(value: Optional[Any], policy: MaskingPolicy) -> Optional[Any]:
    if policy is None:
        raise TypeError("policy must not be None")
    if value is None:
        return None

    strategy = policy.strategy

    if strategy is MaskingStrategy.NONE:
        return value
    if strategy in (MaskingStrategy.FULL, MaskingStrategy.REDACTED):
        return policy.replacement
    if strategy is MaskingStrategy.PARTIAL:
        return _mask_partial(str(value), policy.replacement)
    if strategy is MaskingStrategy.HASH:
        return _mask_hash(str(value), policy.salt)
```

The Java counterpart is `com.enrichmeai.culvert.governance.Masker` (Java
`Masker.java:54–63`): a `switch` over `MaskingStrategy` with identical semantics. The
two are intentionally mirrors of each other — the same default salt, the same
partial-mask rule (last 4 characters kept), the same SHA-256 implementation. A row
masked on the Java Beam path and the same row masked on the Python Airflow path
produce the same hashed value for the same input. That determinism matters when you
are reconciling across layers.


## `PiiMaskingGovernancePolicy`: structural matching\index{PiiMaskingGovernancePolicy}

The single concrete `GovernancePolicy` shipped today identifies PII fields by *column
name*, not by scanning cell values. This is a deliberate scope cap: the class docstring
says so explicitly:

```
Structural only — inspects field names, not values. Tag-based policy resolution
(Dataplex, Cloud DLP, Purview) is out of scope.
```
*(Python `pii_masking_governance_policy.py:39–41`)*

The matching logic is two-stage, applied in order; first match wins:

1. **Exact column-name set** — case-sensitive membership in the `pii_columns`
   `frozenset` supplied at construction. E.g. `{"email", "ssn", "phone"}`.
2. **Regex patterns** — each pattern in `pii_patterns` is tested with
   `re.fullmatch()` (Python) / `Matcher.matches()` (Java). Anchored full-name match,
   so `".*_pii$"` catches `customer_pii` but not `customer_pii_masked`.

A field matching either rule is classified `DataClassification.RESTRICTED`. All other
fields are `DataClassification.INTERNAL`.

Masking policy resolution for a matched field uses the `column_overrides` map first:

```python
# pii_masking_governance_policy.py:107–117

def masking_for(self, field: str, table: str) -> Optional[MaskingPolicy]:
    if not self._is_pii(field):
        return None
    return self._column_overrides.get(field, self._default_masking_policy)
```

The override map is powerful precisely because it is narrow. A single `column_overrides`
entry can give the `phone` column `PARTIAL` masking while every other PII field defaults
to `HASH`. The fraud team gets the last four digits of the phone number; analysts
browsing the mart get the hash. Both decisions are explicit and auditable.

The retention contract is simple: `PiiMaskingGovernancePolicy.retention_for()` always
returns `None`. This policy does not manage retention. If you need table-level
retention, compose it with a second implementation or extend the class — but do not
add cloud SDK calls here. The scope cap is load-bearing.

Here is a representative construction (Java style, from the class Javadoc at
`PiiMaskingGovernancePolicy.java:58–68`):

```java
PiiMaskingGovernancePolicy policy = PiiMaskingGovernancePolicy.builder()
        .piiColumns(Set.of("email", "ssn", "phone"))
        .piiPatterns(List.of(".*_pii$", ".*_secret$"))
        .defaultMaskingPolicy(new MaskingPolicy(MaskingStrategy.FULL, "***", ""))
        .columnOverride("phone", new MaskingPolicy(MaskingStrategy.PARTIAL, "*", ""))
        .build();
```

The same logic in Python (from `pii_masking_governance_policy.py:78–93`):

```python
from data_pipeline_core.governance_api.pii_masking_governance_policy import (
    PiiMaskingGovernancePolicy,
)
from data_pipeline_core.governance_api.policies import MaskingPolicy, MaskingStrategy

policy = PiiMaskingGovernancePolicy(
    pii_columns=frozenset({"email", "ssn", "phone"}),
    pii_patterns=[".*_pii$", ".*_secret$"],
    default_masking_policy=MaskingPolicy(strategy=MaskingStrategy.FULL, replacement="***"),
    column_overrides={"phone": MaskingPolicy(strategy=MaskingStrategy.PARTIAL)},
)
```

Both call the same Protocol methods. A pipeline component that depends on
`GovernancePolicy` by Protocol — not on the concrete class — is unaffected by a future
swap to a Dataplex-backed implementation.


## The data-quality layer

Governance decides what data is sensitive and how it should be protected. Data quality
decides whether the data should be trusted at all. The two concerns are distinct but
connected — you do not want to mask and publish a column that is half-empty — so
Culvert ships them side by side in `data-pipeline-core`.

The quality layer is three types and one transform:

- **`ViolationKind`** — what category of failure was found
- **`FieldViolation`** — the violation, annotated with field name and human-readable detail
- **`ValidationResult`** — either a `ValidRow` or an `InvalidRow` carrying all violations
- **`DataQualityTransform`** — the engine that runs all three checks per row

I will take them in order.


### `ViolationKind`: three categories\index{ViolationKind}

```python
# data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/dataquality/violation_kind.py:14–35

class ViolationKind(Enum):
    MISSING_REQUIRED = "MISSING_REQUIRED"
    TYPE_MISMATCH    = "TYPE_MISMATCH"
    OUT_OF_RANGE     = "OUT_OF_RANGE"
```

Three variants, same names, same semantics in Java (`ViolationKind.java:25–31`) and
Python. `MISSING_REQUIRED` fires when a field declared `mode="REQUIRED"` in the
`EntitySchema` arrives as `None` or is absent from the row map. `TYPE_MISMATCH` fires
when the runtime type of a value does not match the schema wire type (`STRING`,
`INT64`, `FLOAT64`, `BOOL`). `OUT_OF_RANGE` fires when a numeric field falls outside
the closed inclusive range `[min, max]` declared in the schema.\index{ViolationKind!MISSING_REQUIRED}\index{ViolationKind!TYPE_MISMATCH}\index{ViolationKind!OUT_OF_RANGE}


### `NumericRange`: schema-grounded bounds\index{NumericRange}

Range validation is schema-grounded. Bounds live in the `SchemaField` definition, not
in a separate configuration table or a side-map maintained by the pipeline author.
The `NumericRange` record is:

```python
# data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/dataquality/numeric_range.py:14–54

@dataclass(frozen=True)
class NumericRange:
    min: float
    max: float

    @classmethod
    def of(cls, min: float, max: float) -> "NumericRange":
        return cls(min=min, max=max)

    def contains(self, value: float) -> bool:
        return self.min <= value <= self.max
```

You attach it to a field at schema construction time:

```python
SchemaField("amount", "FLOAT64", mode="REQUIRED",
            range=NumericRange.of(0.0, 1_000_000.0))
```

No out-of-band configuration. If the schema says an `amount` field must be between
zero and a million, the transform enforces it — against every row, on every run,
without any further plumbing.


### `FieldViolation` and `ValidationResult`\index{FieldViolation}\index{ValidationResult}

`FieldViolation` is an immutable frozen dataclass carrying the field name, the
`ViolationKind`, and a human-readable `detail` string including expected and actual
values (`field_violation.py:16–49`). It mirrors the Java record
`FieldViolation(String fieldName, ViolationKind violationKind, String detail)`.

`ValidationResult` is the either-type. A row either passes all checks and emerges as a
`ValidRow`, or it fails one or more and emerges as an `InvalidRow` carrying a
non-empty tuple of `FieldViolation` instances. The tuple is immutable — `frozen=True`
on the dataclass mirrors Java's `List.copyOf` — and `InvalidRow` refuses construction
with an empty violation list:

```python
# data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/dataquality/validation_result.py:64–90

@dataclass(frozen=True)
class InvalidRow(ValidationResult[R], Generic[R]):
    violations: Tuple[FieldViolation, ...]

    def __post_init__(self) -> None:
        if len(self.violations) == 0:
            raise ValueError("InvalidRow must have at least one FieldViolation")
```

The full list of violations is preserved. A row that fails three fields gets three
`FieldViolation` entries. This matters in the dead-letter path: if you only see the
first violation you cannot tell whether fixing it will unblock the row or merely
reveal two more failures behind it.


### `DataQualityTransform`: the engine\index{DataQualityTransform}

`DataQualityTransform` is generic over `R` — the row type — and implements the
`Transform` contract. It takes an `EntitySchema`, a `row_accessor` callable that
extracts a field-name-to-value mapping from a row, and an optional `GovernancePolicy`
for post-validation masking. Validation happens in three passes, per field, in order:

1. **`MISSING_REQUIRED`** — if the field's `mode` is `"REQUIRED"` and the value is
   `None` or absent, a violation is recorded and the field is skipped. No further
   checks (type and range) on a missing value.
2. **`TYPE_MISMATCH`** — the wire type is checked against the Python runtime type.
   One subtlety worth knowing: Python's `bool` is a subclass of `int` and therefore
   of `numbers.Number`, but the Java model keeps `Boolean` and `Number` disjoint.
   The Python implementation guards this explicitly (`data_quality_transform.py:88–91`):
   a `True` value fails an `INT64` field with `TYPE_MISMATCH`.
3. **`OUT_OF_RANGE`** — if the `SchemaField` carries a `NumericRange`, the value is
   checked. This check is skipped when the field already has a `TYPE_MISMATCH` flag —
   no point range-checking a value whose type is already wrong.

All violations are accumulated; the transform does not short-circuit on the first
failure. A row with five bad fields produces one `InvalidRow` with five
`FieldViolation` entries.

The `apply()` method wraps the iterator lazily:

```python
# data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/dataquality/data_quality_transform.py:284–317

def apply(
    self,
    records: Iterator[R],
    context: "RuntimeContext",
) -> Iterator[ValidationResult[R]]:
    ...
    return self._validating_generator(records, context)
```

After the iterator is exhausted, one `StageMetrics` snapshot is emitted via
`context.stage_metrics.record_stage_metrics` — `rows_processed`, `error_count`,
and `stage_latency_ms`. Metrics-emission exceptions are swallowed; the framework
does not let monitoring break the pipeline.


### The masking flag — where Python and Java diverge

Here I have to be direct about an asymmetry.

In the Java `DataQualityTransform`, masking is live. After a row passes all
validation checks, the transform calls `Masker.mask()` for each field whose
`GovernancePolicy.maskingFor()` returns a non-empty policy, mutating the row map in
place before wrapping it in a `ValidRow` (`DataQualityTransform.java:86–100`). That
path is complete and tested.

The Python port now matches. After a row passes validation, the transform reads
`governance_policy.masking_for(field, table)` for each field and, where a policy is
returned, applies `governance_api.masker.mask(value, policy)` in place before
returning the `ValidRow` — mirroring the Java path (`data_quality_transform.py:284`):

```python
# data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/dataquality/data_quality_transform.py
from data_pipeline_core.governance_api.masker import mask as _masker_mask
# ... after validation, for each field whose policy is non-None:
            fields[field_name] = _masker_mask(fields[field_name], mp)
```

Earlier in the port (Wave B) this path was a deliberate `NotImplementedError`
stub, because the `DataQualityTransform` and the `Masker` were written by separate
agents who could not see each other; the standalone `masker.py mask()` existed but
was not wired in. That seam was closed at integration (T19.4 / #127): masking now
runs inline on the Python path, end-to-end, with tests proving a classified field
is masked through the transform.\index{DataQualityTransform!masking}


## Dead-letter / quarantine routing\index{quarantine}

`DataQualityTransform` tells you which rows are invalid. It does not decide what to
do with them — that is the dead-letter contract. On the GCP side, the concrete
implementation is `QuarantineHandler` in `data-pipeline-gcp-gcs-java`:

```
<errorPathPrefix>/quarantine/<runId>/<timestamp>.jsonl
```

`QuarantineHandler` serialises the failed rows to newline-delimited JSON in GCS, then
calls `JobControlRepository.markFailed` with the URI of the written file as the
`errorFilePath` (`QuarantineHandler.java:22–60`). The job-control table records
exactly where the bad rows went. The error code is `"DQ_VALIDATION_FAILURE"` and the
failure stage is `FailureStage.VALIDATION`.

The Python orchestration layer has the equivalent via
`data-pipeline-orchestration/callbacks/quarantine.py`, which copies the offending GCS
object into the quarantine bucket under `{reason}/{timestamp}/{blob}` and deletes the
source.

The seam between the transform and the handler is intentional. `DataQualityTransform`
produces `InvalidRow` instances; what your pipeline does with them — quarantine, DLQ
publish, or alert-and-pass — is a pipeline-author decision, not a framework decision.
That separation keeps the core transform reusable across contexts that have different
failure policies.


## What lives above the seam: Dataplex, Cloud DLP, policy tags

I want to be clear about the boundary, because conflating Culvert's governance layer
with GCP's governance services is a frequent source of confusion.\index{governance!layer boundary}

Everything in this chapter so far — `GovernancePolicy`, `PiiMaskingGovernancePolicy`,
`Masker`, `DataClassification`, `DataQualityTransform` — is **cloud-neutral**. None
of those classes import a GCP SDK. They work on any cloud, or in a unit test with no
network access at all. That is the point of the contract seam.

The services that live *above* the seam are not Culvert; they are what you connect a
cloud-specific `GovernancePolicy` implementation to when you outgrow structural
matching:

**BigQuery policy tags**\index{policy tags}\index{BigQuery!policy tags} decide *who can read which column at all*. A policy tag
in BigQuery points at a taxonomy in Dataplex Universal Catalog, and IAM bindings on
the taxonomy node restrict column-level access. A junior analyst with
`bigquery.dataViewer` on a dataset who does `SELECT full_name` against a
`pii_high`-tagged column gets a permission error on that specific column, regardless
of their table-level access. Masking defines *the value*; the policy tag defines *who
sees the unmasked column*. The two are complementary; you want both.

**Cloud DLP / Sensitive Data Protection**\index{DLP}\index{Sensitive Data Protection} is the right tool when you have data
of unknown provenance — an inherited bucket of CSVs, a third-party feed of unknown
shape — and you need automated discovery of PII columns. It is the wrong tool for a
pipeline whose `EntitySchema` already declares which fields are sensitive. Running DLP
across an FDP you know to be masked is paying to relearn what your schema told you for
free. My rule: use DLP for discovery on unknown-schema data; use Culvert's
`PiiMaskingGovernancePolicy` for pipelines where the schema is owned.

**Dataplex Universal Catalog** (the merger of Data Catalog and Dataplex, complete by
2026) provides cataloguing, tagging, quality scoring, and managed lineage.\index{Dataplex} For teams
past about ten data products, the AutoDQ quality score visible on the catalogue entry
— produced by non-engineering stakeholders looking at the Dataplex UI, not the CI
log — is worth running alongside your in-framework validation. But AutoDQ gates
nothing in the pipeline; `DataQualityTransform` gates the pipeline. The two answer
different audiences, not the same question.

A practical adoption sequence: stand up the `PiiMaskingGovernancePolicy` with your
known PII columns, get `DataQualityTransform` running in your pipeline stage, wire
`QuarantineHandler` to the dead-letter bucket. That is week one. Add BigQuery policy
tags for column-level access control in month one. Add Dataplex cataloguing and
AutoDQ in quarter one. Add a richer `GovernancePolicy` implementation — backed by
Dataplex tags — only if structural column-name matching is no longer sufficient. Do
not reach for cloud services before you have exhausted the cloud-neutral layer.


## Honest status

Culvert 0.1.0 (`data-pipeline-core/pyproject.toml:version`) is built and held; nothing
is yet published to PyPI or Maven Central. The governance and data-quality modules
described in this chapter exist, compile, and have test coverage. The one live
asymmetry is the Python `DataQualityTransform` masking flag (T18.2): the standalone
`masker.py` is complete; its integration into the Python transform is not. The Java
side is fully implemented and tested. The pom.xml on the Java module records 1.0.0
as a parent version, but the aligned target for coordinated release is 0.1.0 — do not
cite the pom version as the published artefact version; nothing is published yet.

\begin{takeaways}
\textbf{Key takeaways}
\begin{itemize}
  \item The \texttt{GovernancePolicy} Protocol defines three cloud-neutral methods
    (\texttt{classify}, \texttt{masking\_for}, \texttt{retention\_for}). One concrete
    implementation ships today: \texttt{PiiMaskingGovernancePolicy}, which identifies
    PII fields by exact column-name set and regex patterns — never by cell-value
    inspection.
  \item \texttt{MaskingStrategy} ships five values: \texttt{FULL}, \texttt{PARTIAL}
    (last 4 chars kept), \texttt{REDACTED} (identical to \texttt{FULL} in the
    \texttt{Masker}), \texttt{HASH} (SHA-256 with a constant default salt), and
    \texttt{NONE}. Tokenisation — the strategy fraud and customer-services teams
    ask for — is the honest remaining gap.
  \item \texttt{DataQualityTransform} validates rows against an \texttt{EntitySchema}
    in three passes per field (\texttt{MISSING\_REQUIRED}, \texttt{TYPE\_MISMATCH},
    \texttt{OUT\_OF\_RANGE}) and accumulates all violations before returning. It does
    not short-circuit on the first failure.
  \item The Python \texttt{DataQualityTransform} accepts a \texttt{governance\_policy}
    parameter for API parity with Java, but raises \texttt{NotImplementedError} when
    masking would apply. The Java path is live; the Python masking integration is a
    T18.2 flag. Do not use it in production until the flag is cleared.
  \item Quarantine routing is the pipeline author's decision, not the framework's.
    \texttt{DataQualityTransform} produces \texttt{InvalidRow} results;
    \texttt{QuarantineHandler} (GCS-backed, Java) and the orchestration
    \texttt{quarantine.py} callbacks (Python) are the concrete dead-letter
    implementations.
  \item Culvert's governance layer and GCP's governance services (policy tags,
    Cloud DLP, Dataplex AutoDQ) are complementary, not alternatives. The
    cloud-neutral layer is precise, cheap, and lives inside the pipeline; the
    GCP services are broad, more expensive, and live above it.
\end{itemize}
\end{takeaways}
\newpage

# Chapter 15 — Auto-Config and Discovery

\index{auto-config}\index{discovery}There is a design decision that separates frameworks from libraries, and it is invisible until you have lived on the wrong side of it. A library is something you call. A framework is something that *finds* things for you. For the first three sprints of Culvert, we were building a library: you instantiated `GcsBlobStore` directly, you wired `BigQueryWarehouse` by hand, you passed the concrete class everywhere. The core knew nothing about what was installed. The application code knew everything.

That arrangement works fine when there is one cloud and one engineer who wrote both the pipeline and the adapter. It breaks down the moment you want to ask: *what is available on this classpath, right now?* — and get a meaningful answer without opening the source.

Sprint-4 answered the question. Two mechanisms, one for each language; one contract — `AutoConfig.discover()` — that works identically from the caller's perspective. The seam is where the elegant part lives.

## The problem with explicit wiring

Let me be concrete about what we were doing before. In every pipeline bootstrap, you would see something like this:

```python
from data_pipeline_gcp_gcs import GcsBlobStore
from data_pipeline_gcp_bigquery import BigQueryWarehouse
from data_pipeline_gcp_secrets import SecretManagerProvider

blob = GcsBlobStore(client=storage_client)
wh   = BigQueryWarehouse(project=project, client=bq_client)
sec  = SecretManagerProvider(client=sm_client)
```

The imports are cloud-specific. The module names — `data_pipeline_gcp_gcs`, `data_pipeline_gcp_bigquery` — are leaking into bootstrap code that would otherwise be cloud-neutral. If you want to swap GCS for S3, you find every import, every instantiation, every reference. That is not portability; it is tedium disguised as architecture.

The Java version was the same story. Every `DataflowPipeline` constructor carried a `GcsBlobStore` reference hard-coded at construction time.

The framework-agnostic thesis of Culvert demands better. If the contracts are cloud-neutral, the *wiring* should be too. The application should be able to say: "give me whatever `BlobStore` is installed" — and trust the runtime to answer.

## Python: entry-points and the adapter group

\index{entry-points}Python has had a solution to this problem since PEP 517, formalized in `importlib.metadata`: **entry-points**. Every installed Python distribution can declare named hooks under a group, and `importlib.metadata.entry_points()` can enumerate them without importing the module.

Culvert defines one group:

```toml
# data-pipeline-gcp-secrets/pyproject.toml:36
[project.entry-points."data_pipeline_core.adapters"]
secrets = "data_pipeline_gcp_secrets:SecretManagerProvider"
```

The key is `secrets`. The value resolves to the class. The group is `data_pipeline_core.adapters` — a string the *core* owns, declared in no GCP-specific module. When the `data-pipeline-gcp-secrets` distribution is installed, pip writes this mapping into the package metadata. Nothing else is needed. The adapter has announced itself.

The BigQuery adapter announces two things — a `Warehouse` implementation and a `FinOpsSink` — in one block:

```toml
# data-pipeline-gcp-bigquery/pyproject.toml:44
[project.entry-points."data_pipeline_core.adapters"]
warehouse = "data_pipeline_gcp_bigquery:BigQueryWarehouse"
finops    = "data_pipeline_gcp_bigquery:BigQueryFinOpsSink"
```

GCS announces one:

```toml
# data-pipeline-gcp-gcs/pyproject.toml:30
[project.entry-points."data_pipeline_core.adapters"]
blob_store = "data_pipeline_gcp_gcs:GcsBlobStore"
```

The entry-point key — `secrets`, `warehouse`, `blob_store` — maps directly to a field name on the `AutoConfig` dataclass. That naming discipline is the load-bearing piece. It is what lets `discover()` be a ten-line loop instead of a lookup table.

## `discover()` — the registry builder

\index{AutoConfig.discover()}`discover()` lives in `data_pipeline_core.autoconfig` — the Python core — and it imports nothing from any cloud module:

```python
# data-pipeline-core/src/data_pipeline_core/autoconfig.py:85
def discover() -> AutoConfig:
    config = AutoConfig()
    config._process_overrides = dict(_REGISTRY._process_overrides)
    eps = entry_points()
    try:
        group_entries = eps.select(group=ENTRY_POINT_GROUP)
    except AttributeError:
        group_entries = eps.get(ENTRY_POINT_GROUP, [])

    for ep in group_entries:
        try:
            cls = ep.load()
        except Exception as exc:
            logger.warning(
                "Failed to load entry-point %s = %s: %s",
                ep.name, ep.value, exc,
            )
            continue
        field_list = getattr(config, ep.name, None)
        if field_list is None:
            logger.warning("Unknown adapter contract '%s' ...", ep.name, ep.value)
            continue
        field_list.append(cls)
    return config
```

Walk the group, `ep.load()` to get the class (no instantiation — the adapter almost certainly needs constructor arguments that `discover()` cannot know), append to the matching field. One line handles the Python 3.10+/earlier API difference. Unknown entry-point names produce a warning, not an exception — future adapters with new contracts will not crash old code.

The `AutoConfig` dataclass holds one `List[Type[Any]]` per contract:\index{AutoConfig fields}

```python
# data-pipeline-core/src/data_pipeline_core/autoconfig.py:48
@dataclass
class AutoConfig:
    warehouse:     List[Type[Any]] = field(default_factory=list)
    blob_store:    List[Type[Any]] = field(default_factory=list)
    source:        List[Type[Any]] = field(default_factory=list)
    sink:          List[Type[Any]] = field(default_factory=list)
    transform:     List[Type[Any]] = field(default_factory=list)
    secrets:       List[Type[Any]] = field(default_factory=list)
    job_control:   List[Type[Any]] = field(default_factory=list)
    finops:        List[Type[Any]] = field(default_factory=list)
    observability: List[Type[Any]] = field(default_factory=list)
    lineage:       List[Type[Any]] = field(default_factory=list)
    audit:         List[Type[Any]] = field(default_factory=list)
    governance:    List[Type[Any]] = field(default_factory=list)
    pipeline:      List[Type[Any]] = field(default_factory=list)
    runtime:       List[Type[Any]] = field(default_factory=list)
    stage_metrics: List[Type[Any]] = field(default_factory=list)
```

Fifteen contracts; fifteen fields. The `stage_metrics` field was the last to arrive, added when `StageMetricsHook` landed in Sprint-12. Each name matches an entry-point key, which matches a contract module name in `data_pipeline_core.contracts.*`. That is the discipline that makes the whole mechanism work without a lookup table.

The `ENTRY_POINT_GROUP` constant at line 34 is the single definition of the group name. If we ever rename it, one edit cascades correctly.

`AutoConfig.first()` and `AutoConfig.all()` are the two lookup methods a pipeline author actually calls:

```python
# data-pipeline-core/src/data_pipeline_core/autoconfig.py:70
def first(self, name: str) -> Optional[Type[Any]]:
    impls = self.all(name)
    return impls[0] if impls else None

def all(self, name: str) -> List[Type[Any]]:
    return list(self._process_overrides.get(name, [])) + list(getattr(self, name, []))
```

In-process overrides come first (more on those shortly); discovered impls follow. If nothing is installed, `first()` returns `None` rather than raising — the caller decides whether that is fatal.

## Java: ServiceLoader and `META-INF/services`

\index{ServiceLoader}Java has had the equivalent mechanism since JDK 1.6: `ServiceLoader`. Instead of `pyproject.toml` entry-points, each adapter module ships a file at `META-INF/services/<fully.qualified.ContractInterface>` containing the fully-qualified implementation class name.

The GCS adapter registration looks like this:

```
# data-pipeline-gcp-gcs-java/src/main/resources/META-INF/services/
# com.enrichmeai.culvert.contracts.BlobStore
com.enrichmeai.culvert.gcp.gcs.GcsBlobStore
```

The BigQuery adapter registers four implementations across four files — `Warehouse`, `FinOpsSink`, `JobControlRepository`, `AuditEventPublisher`. The secrets adapter registers one:

```
# data-pipeline-gcp-secrets-java/src/main/resources/META-INF/services/
# com.enrichmeai.culvert.contracts.SecretProvider
com.enrichmeai.culvert.gcp.secrets.SecretManagerProvider
```

Java's `AutoConfig` in `data-pipeline-core-java` discovers them via `ServiceLoader.load()`:

```java
// data-pipeline-core-java: AutoConfig.java:96
public static AutoConfig discover() {
    return new AutoConfig();
}

// ... in the private constructor (AutoConfig.java:71):
this.blobStores    = loadServiceList(BlobStore.class);
this.warehouses    = loadServiceList(Warehouse.class);
this.secretProviders = loadServiceList(SecretProvider.class);
// ... and twelve more
```

The helper method:

```java
// data-pipeline-core-java: AutoConfig.java:221
private static <T> List<T> loadServiceList(Class<T> contract) {
    List<T> impls = new ArrayList<>();
    try {
        for (T impl : ServiceLoader.load(contract)) {
            impls.add(impl);
        }
    } catch (Throwable ignored) {
        // ServiceConfigurationError from missing no-arg constructors:
        // sprint-4 limitation.
    }
    return List.copyOf(impls);
}
```

That `catch (Throwable ignored)` is honest and a bit uncomfortable. Here is why it exists.

`ServiceLoader` instantiates impls via their **no-arg constructor**. Most production adapters — `BigQueryWarehouse`, `GcsBlobStore` — need constructor arguments: a GCP project ID, a client object, credentials. They do not have no-arg constructors. ServiceLoader hits `ServiceConfigurationError`. The catch swallows it silently.

The META-INF file for `BigQueryWarehouse` includes a comment acknowledging this directly:

```
# data-pipeline-gcp-bigquery-java/src/main/resources/META-INF/services/
# com.enrichmeai.culvert.contracts.Warehouse

# Pre-registered for sprint-4 auto-config. The implementation does NOT
# expose a no-arg constructor — BigQuery requires project + location +
# credentials at construction time. Direct ServiceLoader.load(
# Warehouse.class).findFirst() will fail with ServiceConfigurationError
# until a config-driven constructor is introduced. Until then,
# instantiate explicitly with `new BigQueryWarehouse(projectId, client)`.
com.enrichmeai.culvert.gcp.bigquery.BigQueryWarehouse
```

Which adapters *do* resolve at v0.1.0? The ones with a no-arg constructor. `SecretManagerProvider` was built with one from day one — Secret Manager's client picks up Application Default Credentials automatically, so there is genuinely nothing to pass at construction. Similarly, `CloudTraceObservabilityHook` gained a no-arg constructor in Sprint-12 (#91) that wraps `GlobalOpenTelemetry.get()` — the tracing SDK wires the exporter separately. Those two resolve cleanly. The warehouse, blob store, and job control adapters are pre-registered but silent until a future config-driven instantiation wave arrives.

The difference from Python is meaningful: Python `discover()` returns *classes* and never instantiates them — so the Python registry resolves the full installed set regardless of constructor shape. The Java registry resolves only the no-arg-friendly subset at v0.1.0. That asymmetry is real, and worth being honest about.

## The `@register_adapter` escape hatch

\index{register\_adapter}Both registration mechanisms — entry-points and META-INF/services — work at package-install time. For testing and in-process demos you need something faster: a way to register a fake implementation without packaging it.

Python provides that via the `@register_adapter` decorator:

```python
# data-pipeline-core/src/data_pipeline_core/autoconfig.py:119
def register_adapter(contract_name: str):
    def decorator(cls):
        _REGISTRY._process_overrides.setdefault(contract_name, []).append(cls)
        return cls
    return decorator
```

Usage in a test:

```python
from data_pipeline_core.autoconfig import register_adapter

@register_adapter("warehouse")
class FakeWarehouse:
    def query(self, sql, params=None): return []
    def execute(self, sql, params=None): pass
    # ...
```

The process-wide `_REGISTRY` accumulates these overrides. When `discover()` runs, it seeds the new `AutoConfig` with a copy of those overrides before walking entry-points — so in-process registrations win over anything installed. `reset_process_registry()` at line 142 clears them between tests.

This three-tier resolution — in-process override → entry-point discovery — keeps the testing experience clean without requiring test distributions with real `pyproject.toml` declarations.

## Why the core stays clean

\index{cloud-neutral core}The entire mechanism hinges on a property that is easy to state and surprisingly hard to preserve: `data_pipeline_core` has no imports from any cloud module. `autoconfig.py` imports only `importlib`, `logging`, `dataclasses`, and `importlib.metadata.entry_points`. That is the standard library. The `AutoConfig` class imports only `data_pipeline_core.contracts.*` — the neutral interfaces. No `google-cloud-*` anywhere.

This is the same principle the v1 framework enforced for Beam and Airflow: the foundation library has no runtime dependency on the execution substrate. The v1 chapter described the reasoning: a foundation that imports Beam means your Airflow operators pull Beam in; your unit tests spin up Beam runners; your CI gets slow; your Cloud Functions cold-start lasts forty seconds. The same applies here. A foundation that imports `google-cloud-bigquery` means any tool that uses the registry drags in the BigQuery SDK, its gRPC transport, its auth libraries, and half of `google-auth`. The whole point of the adapter pattern is that cloud-specific code lives behind cloud-specific packages, and the core stays ignorant.

The entry-point mechanism enforces this structurally. The core declares the group name (`ENTRY_POINT_GROUP = "data_pipeline_core.adapters"`). Cloud packages declare membership. The act of declaring membership imports nothing — it is metadata written into the distribution's package info at install time. Only when `ep.load()` is called does the cloud module's code execute, and by then you have already decided to use that adapter.

## The real history: adapters existed before the registry

\index{discovery!history}One thing worth naming honestly: the mechanism and the adapters did not arrive simultaneously. Sprint-3 (May 2026) delivered `GcsBlobStore`, `BigQueryWarehouse`, and the PubSub adapters — three working Python implementations with tests, no entry-points. Sprint-4 delivered `autoconfig.py` and `discover()` — the registry mechanism, with no adapters wired into it. The two halves existed independently for several weeks.

The core GCS, BigQuery, and PubSub Python adapters did not declare their entry-points until commit #126 (June 2026), when the Wave C cost-tracker work wired them up as discoverable. The `data-pipeline-gcp-secrets` Python adapter got its entry-point in #124 (June 2026) when the adapter itself was created. So for the window between sprint-4 and wave-C, `discover()` would have returned an empty registry — the mechanism worked, but there was nothing to find.

That ordering is not a design failure; it is how real frameworks develop. You build the mechanism first and prove it works on the contract tests. You wire the adapters once there is something to wire. The Java side had the same pattern: META-INF service files were pre-registered early, but most of the impls lack no-arg constructors so the registry is partially populated until config-driven instantiation lands.

## Using the registry

When everything is wired, the caller's code looks like this in Python:

```python
from data_pipeline_core.autoconfig import discover

config = discover()
WarehouseClass = config.first("warehouse")
if WarehouseClass is None:
    raise RuntimeError("No Warehouse adapter on the import path")
wh = WarehouseClass(project=project_id, client=bq_client)
```

And in Java:

```java
// data-pipeline-core-java: AutoConfig.java:36 (Javadoc example)
AutoConfig config = AutoConfig.discover();
Warehouse warehouse = config.warehouse()
    .orElseThrow(() -> new IllegalStateException("No Warehouse on classpath"));
```

The pipeline code has zero imports from `data_pipeline_gcp_*`. It names only `data_pipeline_core`. Swap the installed distribution — swap the entire cloud — and nothing in the pipeline changes. That is the story the entry-point mechanism makes possible.

## What is not there yet

\index{config-driven instantiation}Two gaps remain at v0.1.0.

First, **config-driven instantiation**. `discover()` returns classes, not instances. You still have to call the constructor yourself and pass the right arguments. The Javadoc at `AutoConfig.java:44` calls this out: "Sprint-5 adds config-driven instantiation." The Python docstring at `autoconfig.py:18` makes the same note. At time of writing that sprint has not yet run. Wiring constructor arguments from a config file — project ID, service account, region — is the next layer.

Second, **the no-arg gap on the Java side**. Until config-driven instantiation lands, Java's `discover()` silently skips impls that need constructor arguments. The registry returns empty `Optional.empty()` for warehouse, blob store, and job control, even when those modules are on the classpath. That is documented, not hidden — but it is a real limitation.

Both will be fixed. Culvert is built and held at 0.1.0, nothing published to Maven Central or PyPI yet. The coordinated release (both Java and Python, together) gates on both being ready. When it ships, these gaps will be closed.

\begin{takeaways}
\textbf{Key takeaways}
\begin{itemize}
  \item Python discovery uses \texttt{importlib.metadata} entry-points under the \texttt{data\_pipeline\_core.adapters} group. The entry-point \emph{key} (\texttt{secrets}, \texttt{warehouse}, \texttt{blob\_store}) maps directly to the \texttt{AutoConfig} field name. One \texttt{pyproject.toml} block is all an adapter needs.
  \item Java discovery uses \texttt{ServiceLoader} with \texttt{META-INF/services/<ContractInterface>} files. The mechanism is identical in intent; the file format reflects Java's classpath convention.
  \item The two mechanisms differ in an important detail at v0.1.0: Python \texttt{discover()} returns classes and never instantiates them, so the full installed set resolves. Java \texttt{discover()} instantiates via no-arg constructor and silently skips adapters that lack one — which is most GCP adapters. Config-driven instantiation is the next wave.
  \item \texttt{data\_pipeline\_core} has no runtime imports from any cloud module. The entry-point mechanism enforces this: declaring membership in the group costs nothing at import time. Cloud code only executes when \texttt{ep.load()} is called.
  \item The \texttt{@register\_adapter} decorator provides in-process registration for tests and demos. It wins over entry-point discoveries and can be cleared between tests with \texttt{reset\_process\_registry()}.
  \item The mechanism and the adapters did not arrive simultaneously. The registry landed Sprint-4; the GCS/BigQuery/PubSub Python adapters did not declare entry-points until Wave~C. A working mechanism with nothing to find is still a working mechanism — the gap is wiring, not architecture.
\end{itemize}
\end{takeaways}

\newpage

# Chapter 16 — Contract Testing as the Safety Net

Here is something I could not write convincingly until I had built more than one adapter: **a test suite is only as strong as what it binds to**. In the predecessor framework the tests were numerous — and they were unit tests, each scoped to the class that wrote them. If `GcsBlobStore.get` had a latent bug, GCS's own tests would catch it. But nobody was forcing `GcsBlobStore` to answer the same questions as any future `S3BlobStore`. They could diverge silently, and you would not find out until you switched clouds.

Culvert's answer is the contract test: a shared suite of assertions that every adapter for a given contract must inherit and pass. The suite is a dependency, not a convention. Conformance is enforced by subclassing, not by reviewing the README.

## The shape of the problem

When you define a language-neutral contract — say, `BlobStore` — you are making a promise about behaviour: `get` returns the bytes at a URI; `delete` on a missing object is idempotent; `null` arguments are refused at the boundary. The contract interface captures the types. It does not capture those behavioural invariants. Without a shared test suite, each adapter author re-invents the assertions (or forgets them), and behavioural drift accumulates quietly.

Contract tests are the standard answer to this. The mechanism is not new — JUnit's `@Test` on an abstract class has been possible for years, and pytest's mixin pattern is older still. What Culvert formalises is the pairing: every abstract class or mixin in `data-pipeline-contract-tests-java` and `data-pipeline-contract-tests` (Python) is shipped as a test-support library that adapters list as a dependency. The adapter module *inherits* the suite; the adapter author supplies only the wiring.

## The Java side: abstract base classes

Three abstract classes live in `data-pipeline-libraries-java/data-pipeline-contract-tests-java/src/main/java/com/enrichmeai/culvert/contracttests/`:

`BlobStoreContractTest` \index{BlobStoreContractTest}, `SecretProviderContractTest` \index{SecretProviderContractTest}, and `WarehouseContractTest` \index{WarehouseContractTest}. Each follows the same structure: the class is abstract, there are one or more abstract factory methods the subclass must implement (returning the SUT, pre-configured to a known state), and the test methods are concrete — inherited verbatim by every adapter.

`BlobStoreContractTest` is the simplest to read:

```java
// data-pipeline-contract-tests-java/src/main/java/com/enrichmeai/culvert/contracttests/BlobStoreContractTest.java:18-53
public abstract class BlobStoreContractTest {

    protected abstract BlobStore store();
    protected abstract String knownUri();
    protected abstract String missingUri();

    @Test
    void getKnownReturnsBytes() {
        byte[] data = store().get(knownUri());
        assertThat(data).isEqualTo("hello".getBytes());
    }

    @Test
    void existsKnownTrue() {
        assertThat(store().exists(knownUri())).isTrue();
    }

    @Test
    void existsMissingFalse() {
        assertThat(store().exists(missingUri())).isFalse();
    }

    @Test
    void deleteMissingIsIdempotent() {
        store().delete(missingUri());
    }

    @Test
    void nullArgumentsRejected() {
        assertThatThrownBy(() -> store().get(null))
                .isInstanceOfAny(NullPointerException.class, IllegalArgumentException.class);
    }
}
```

Five tests. The adapter author provides `store()`, `knownUri()`, and `missingUri()`, configures the mock (or real) backend to match those preconditions, and all five run automatically. Notice what `nullArgumentsRejected` asserts: the adapter must reject `null` at the public entry point, not somewhere downstream. That particular assertion is one we will return to in a moment, because it is the test that surfaces a class of bug the adapter's own unit tests often miss.

`SecretProviderContractTest` is similarly small — three tests: `getKnownSecretReturnsValue`, `getMissingSecretThrowsNoSuchElement`, and `nullNameRejected`. The abstract factory is `provider()`, and the contract comment even includes example wiring:

```java
// SecretProviderContractTest.java:20-30
class SecretManagerProviderContractTest extends SecretProviderContractTest {
    protected SecretProvider provider() {
        SecretManagerServiceClient client = mockClient(
            Map.of("known-secret", "the-secret-value"));
        return new SecretManagerProvider("my-project", client);
    }
}
```

That is the entire subclass. The boilerplate is in the base; the adapter author writes only what is specific to their adapter.

`WarehouseContractTest` is the richest of the three and has the most interesting evolution. The base defines four tests — `queryStreamsRows`, `tableExistsTrueForKnown`, `tableExistsFalseForMissing`, and `nullSqlRejected` — and a pair of overridable hooks:

```java
// WarehouseContractTest.java:44-56
protected String knownTable() {
    return "contract_test_table";
}

protected String missingTable() {
    return "contract_missing_table";
}
```

Those hooks exist because BigQuery rejected the default bare table name. BigQuery requires fully-qualified names in `dataset.table` or `project.dataset.table` form; feeding it a bare `contract_test_table` produces a parse-time error before the contract test even gets to its first assertion. The contract base had to grow an escape hatch: T15.4 added `knownTable()` and `missingTable()` as protected methods so a BigQuery subclass could supply `contract_ds.contract_test_table` without touching the inherited assertions. The base remains cloud-neutral; the adapter overrides only what its cloud makes necessary.

`BigQueryWarehouseContractTest` wires this up in fourteen lines of real code, plus a mock:

```java
// data-pipeline-gcp-bigquery-java/.../BigQueryWarehouseContractTest.java:45-100
class BigQueryWarehouseContractTest extends WarehouseContractTest {

    private static final String KNOWN_TABLE  = "contract_ds.contract_test_table";
    private static final String MISSING_TABLE = "contract_ds.contract_missing_table";

    @Override
    protected String knownTable()   { return KNOWN_TABLE; }

    @Override
    protected String missingTable() { return MISSING_TABLE; }

    @Override
    protected Warehouse warehouse() {
        BigQuery client = mock(BigQuery.class);
        // ... stub query() to return one row {id: "1"} ...
        // ... stub getTable(KNOWN_TABLE) → non-null, getTable(MISSING_TABLE) → null ...
        return new BigQueryWarehouse(PROJECT_ID, client);
    }
}
```

No Testcontainers. No real GCP credentials. The mock supplies the preconditions the base specifies; the four inherited contract tests run in a normal CI job.

## The Python side: pytest mixins

Python has no abstract base classes in the JUnit sense, but pytest has a composable pattern that achieves the same result: the mixin class defines test methods that rely on pytest fixtures. The fixture is not defined in the mixin — the subclass provides it. The framework's four mixins live in `data-pipeline-libraries/data-pipeline-contract-tests/src/data_pipeline_contract_tests/`:

- `BlobStoreContract` — fixtures `store`, `known_uri`, `missing_uri`; five tests, 1:1 with the Java base
- `SecretProviderContract` — fixture `provider`; three tests
- `WarehouseContract` — fixture `warehouse`; four tests
- `StageMetricsHookContract` — fixtures `hook` and `failing_hook`; five tests

`BlobStoreContract` mirrors the Java class almost exactly:

```python
# data-pipeline-contract-tests/src/data_pipeline_contract_tests/blob_store.py:11-34
class BlobStoreContract:
    def test_get_known_returns_bytes(self, store, known_uri):
        assert store.get(known_uri) == b"hello"

    def test_exists_known_true(self, store, known_uri):
        assert store.exists(known_uri) is True

    def test_exists_missing_false(self, store, missing_uri):
        assert store.exists(missing_uri) is False

    def test_delete_missing_idempotent(self, store, missing_uri):
        store.delete(missing_uri)

    def test_null_arguments_rejected(self, store):
        with pytest.raises((TypeError, ValueError)):
            store.get(None)
```

The mixin is just a plain Python class. Any test class that inherits from it and provides the required fixtures gets the full suite.

`TestGcsBlobStoreContract` in `data-pipeline-gcp-gcs/tests/test_blob_store.py` binds it in one line:

```python
# data-pipeline-gcp-gcs/tests/test_blob_store.py:22
class TestGcsBlobStoreContract(BlobStoreContract):
    @pytest.fixture
    def store(self):
        # ... mock client wired to return b"hello" for known_uri ...
        return GcsBlobStore(client)

    @pytest.fixture
    def known_uri(self):
        return "gs://test-bucket/path/known"

    @pytest.fixture
    def missing_uri(self):
        return "gs://test-bucket/path/missing"
```

`TestBigQueryWarehouseContract` in `data-pipeline-gcp-bigquery/tests/test_warehouse.py` does the same for the warehouse. `TestSecretManagerProviderContract` in `data-pipeline-gcp-secrets/tests/test_secret_manager_provider.py` handles secrets.

The cloud observability adapter also binds `StageMetricsHookContract` in `data-pipeline-gcp-observability/tests/test_cloud_monitoring_metrics_hook.py`. That mixin deserves its own note.

## The StageMetricsHookContract: swallow and continue

`StageMetricsHookContract` is the one Python mixin with no direct Java equivalent. The Java side has `StageMetricsHook` as an interface with a stated behavioural contract — "implementations must not propagate monitoring-backend failures to the caller" — but there is no abstract `StageMetricsHookContractTest` in the Java library at version 0.1.0. The Python mixin exists; the Java base does not (yet).

What the Python mixin tests that the others do not is the *resilience guarantee*:

```python
# data-pipeline-contract-tests/src/data_pipeline_contract_tests/stage_metrics_hook.py:93-101
def test_backend_failure_is_swallowed(self, failing_hook):
    """Core contract guarantee: if the monitoring backend is unavailable
    the implementation must NOT propagate the exception to the caller.
    The pipeline continues uninterrupted.
    """
    # Must not raise even though the backend raises internally.
    failing_hook.record_stage_metrics(_valid_metrics())
```

The `failing_hook` fixture is an instance of the same adapter wired to a backend that raises on every call. The test passes only if the adapter swallows the exception. That invariant is easy to state in an interface comment and easy to forget in an implementation; the mixin is the difference between an assertion that is checked on every CI run and one that lives only in the docs.

## The test that catches what unit tests miss

Here is the story the `nullSqlRejected` test tells, and it is worth telling precisely.

The Python `WarehouseContract` mixin defines:

```python
# data-pipeline-contract-tests/src/data_pipeline_contract_tests/warehouse.py:33-36
def test_null_sql_rejected(self, warehouse):
    with pytest.raises((TypeError, ValueError)):
        warehouse.query(None)
```

Notice: it calls `warehouse.query(None)` and asserts an exception — **without iterating the result**. If `query` returns a generator, and the null check lives inside the generator body, the exception defers until the caller iterates. The test — which does not iterate — passes. The bug lives on.

Now look at `BigQueryWarehouse.query` as it stands today:

```python
# data-pipeline-gcp-bigquery/src/data_pipeline_gcp_bigquery/warehouse.py:30-45
def query(self, sql, params=None):
    """...
    Argument validation is eager (runs before any iteration) so that
    ``query(None)`` raises immediately rather than only when the caller
    first iterates the returned generator.  This matches the Java
    contract (``nullSqlRejected``) and is required for
    ``WarehouseContract.test_null_sql_rejected``.
    """
    if sql is None:
        raise TypeError("sql must not be None")
    return self._query_rows(sql, params)

def _query_rows(self, sql, params=None):
    """Inner generator — called only after sql has been validated."""
    job = self.client.query(sql)
    ...
    yield dict(row.items()) if hasattr(row, "items") else dict(row)
```

The null check is in `query`. The generator is in `_query_rows`. The split is deliberate; the docstring says so explicitly. The reason it is deliberate is that the contract test is stricter than the adapter's own unit test: `test_warehouse.py:136-139` calls `list(w.query(None))`, which forces iteration and so would pass even with a lazy guard. `test_null_sql_rejected` does not iterate — and therefore fails if the guard is inside the generator. The contract test was the diagnostic.

The Java `WarehouseContractTest.nullSqlRejected` makes the same demand:

```java
// WarehouseContractTest.java:78-81
@Test
void nullSqlRejected() {
    assertThatThrownBy(() -> warehouse().query(null, Map.of()))
            .isInstanceOfAny(NullPointerException.class, IllegalArgumentException.class);
}
```

No iteration. The Java `BigQueryWarehouse.query` also validates eagerly, before building the `QueryJobConfiguration` — guaranteed by `Objects.requireNonNull(sql, ...)` on the first line of the method body.

This is the thesis in miniature: **a shared contract test can be stricter than any single adapter's hand-written test.** The adapter test was reasonable; it just made a slightly different assumption about how `query(null)` would be exercised. The contract test made none.

## Current bindings: who is inside the net

At version 0.1.0, the following adapter modules bind the contract bases:

**Java (`extends *ContractTest`):**

| Adapter class | Contract base | Source |
|---|---|---|
| `GcsBlobStore` | `BlobStoreContractTest` | `data-pipeline-gcp-gcs-java/.../GcsBlobStoreContractTest.java` |
| `BigQueryWarehouse` | `WarehouseContractTest` | `data-pipeline-gcp-bigquery-java/.../BigQueryWarehouseContractTest.java` |
| `SecretManagerProvider` | `SecretProviderContractTest` | `data-pipeline-gcp-secrets-java/.../GcpSecretManagerContractTest.java` |

**Python (`class Test*(Contract)`):**

| Adapter class | Contract mixin | Source |
|---|---|---|
| `GcsBlobStore` | `BlobStoreContract` | `data-pipeline-gcp-gcs/tests/test_blob_store.py` |
| `BigQueryWarehouse` | `WarehouseContract` | `data-pipeline-gcp-bigquery/tests/test_warehouse.py` |
| `SecretManagerProvider` | `SecretProviderContract` | `data-pipeline-gcp-secrets/tests/test_secret_manager_provider.py` |
| `CloudMonitoringMetricsHook` | `StageMetricsHookContract` | `data-pipeline-gcp-observability/tests/test_cloud_monitoring_metrics_hook.py` |

There is one gap worth naming: the AWS (`S3BlobStore`) and Azure (`AzureBlobStore`) skeleton adapters each have a hand-rolled test class — `S3BlobStoreTest` and `AzureBlobStoreTest` — that does not inherit from `BlobStoreContractTest`. Those unit tests cover construction and the obvious happy paths, but they do not currently assert idempotent delete or eager null-rejection in a way that would be caught by the contract base. When those adapters graduate from skeleton to production-grade, binding the contract base is the first task, not the last.

## The architecture that makes it a net, not a guideline

The mechanism matters as much as the intention. Three things turn this from a convention into an enforced constraint.

**First, the base classes and mixins are shipped in a dedicated library, not in the adapter itself.** `data-pipeline-contract-tests-java` is a Maven module other modules can declare a test-scope dependency on. `data-pipeline-contract-tests` is an installable Python package. When an adapter module pulls it in and subclasses the base, the entire suite runs as part of that module's ordinary test pass. There is no separate "run the contract tests" step to remember.

**Second, the subclass must supply the SUT in a specified, documented state.** This is where naive contract testing breaks down: the suite asserts things like "delete a missing object does not throw," which requires the mock to be wired to simulate a missing object correctly. If you supply a mock that returns success for every call, `deleteMissingIsIdempotent` passes whether the adapter handles the 404 or not. The contract bases document the preconditions in their Javadoc and class docstrings explicitly. Supplying a mis-wired SUT is the adapter author's error; the suite cannot save you from that. But it can — and does — refuse to compile if you forget to provide the factory method.

**Third, CI runs the adapter module's tests on every pull request.** The contract suite runs when the adapter's test target runs. There is no second CI job, no separate gate, no way to merge an adapter change that breaks a contract method without a red build.

## What the net does not catch

Two things the contract tests cannot do.

They cannot catch subtle semantic mismatches that fall inside the documented preconditions. `BlobStoreContractTest` verifies that `get(knownUri())` returns bytes equal to `"hello".getBytes()`. It does not verify character encoding, content-type negotiation, or partial-read behaviour on large objects. Those are adapter-specific concerns; if they matter, the adapter should have additional adapter-specific unit tests.

They cannot enforce the contract on adapters that do not subclass the base. The AWS and Azure skeletons demonstrate this gap. The safety net has a hole where the non-GCP adapters currently stand. The hole is documented, not ignored; but documentation is not a test.

\begin{takeaways}
\textbf{Key takeaways}
\begin{itemize}
  \item Contract tests are a shared suite of behavioural assertions that every adapter for a given contract must inherit and pass. In Culvert v0.1.0: three Java abstract classes in \texttt{data-pipeline-contract-tests-java} (\texttt{BlobStoreContractTest}, \texttt{SecretProviderContractTest}, \texttt{WarehouseContractTest}); four Python mixins in \texttt{data-pipeline-contract-tests} (\texttt{BlobStoreContract}, \texttt{SecretProviderContract}, \texttt{WarehouseContract}, \texttt{StageMetricsHookContract}).
  \item Conformance is enforced by subclassing, not by convention. An adapter module that pulls in the contract-test library and extends the base class gets the full suite in its ordinary CI test pass. No separate gate to remember.
  \item A shared contract test can be stricter than any single adapter's hand-written unit test. The \texttt{nullSqlRejected} case is the cleanest example: the mixin calls \texttt{query(None)} without iterating, failing a lazy guard; the adapter's own test called \texttt{list(query(None))}, which forced iteration and would have passed a lazy guard. The contract test diagnosed the design flaw; the adapter test would have missed it.
  \item \texttt{StageMetricsHookContract} also tests the resilience guarantee — that monitoring backend failures must not propagate to the caller — which is exactly the kind of invariant an interface comment states and an implementation forgets.
  \item The AWS (\texttt{S3BlobStore}) and Azure (\texttt{AzureBlobStore}) skeleton adapters have hand-rolled unit tests that do not inherit the contract base. When those adapters graduate from skeleton to production-ready, binding \texttt{BlobStoreContractTest} is the first task, not a follow-up.
\end{itemize}
\end{takeaways}

\newpage

# End-to-End Testing, Tracing, and the Developer Workflow

The previous chapter was about the contract tests — the safety net that proves an adapter conforms. This one is about the loop you actually live in: build, test, run, trace, repeat. A framework is only as pleasant as its inner loop, and because Culvert is polyglot the loop has a Java half and a Python half that deliberately feel the same.

## The inner loop

**Java.** The reactor builds and unit-tests in one command (`README.md`):

```bash
mvn -f data-pipeline-libraries-java/pom.xml install        # build + unit tests, all modules
mvn -f data-pipeline-libraries-java/pom.xml -pl data-pipeline-gcp-bigquery-java -am test   # one module
```

**Python.** Each package is an independent distribution; install it editable and run pytest:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e data-pipeline-libraries/data-pipeline-core pytest
pytest data-pipeline-libraries/data-pipeline-core/tests
```

Unit tests need no cloud and no credentials — that is the point of the contract seam. You test business logic against in-memory adapters and never touch a real bucket.

## The emulator tier

Unit-green does not prove the adapters talk to their clouds correctly. That is what the integration tier is for. `data-pipeline-it-support-java` provides Testcontainers-backed GCP emulators (BigQuery, fake-GCS, the Pub/Sub emulator), and the `it` Maven profile runs the `*IT.java` tests against them:

```bash
mvn -f data-pipeline-libraries-java/pom.xml -P it verify   # needs a running Docker daemon
```

No GCP project, no service-account key — all traffic goes to localhost containers the tests start and stop. This is the tier that catches "my SQL was subtly wrong" without a cloud bill, and it is the one I insist runs before anything is called done.

## Tracing a run end to end

When a run misbehaves, you do not want to read six services' logs. Culvert threads a single `run_id` through the whole pipeline via `RuntimeContext`, and the `ObservabilityHook` contract (Cloud Trace on GCP, per Chapter [Observability and Lineage]) emits a span per stage keyed to it. One `run_id` gives you the end-to-end story: which stage, how many rows, where it failed — from the audit trail alone, which is exactly how you want to debug at 3 a.m.

## Where CI fits

The same two tiers are the CI gate (`.github/workflows/ci.yml`): a per-module Java matrix plus the Python tests run first; the emulator `java-it` tier runs only if they pass; a final gate fans in. The workflow is committed but **disabled at the GitHub level** during development (an engineer enables it deliberately) — the same commands you run locally are the ones CI runs, which is the property that keeps "works on my machine" honest.

\begin{takeaways}
\textbf{Key takeaways}
\begin{itemize}
  \item The inner loop is symmetric across languages: \texttt{mvn ... install} / \texttt{-pl ... test} for Java, \texttt{pip install -e} + \texttt{pytest} for Python. Unit tests need no cloud or credentials.
  \item The emulator tier (\texttt{data-pipeline-it-support-java} + \texttt{mvn -P it verify}) exercises adapters against Testcontainers GCP emulators on localhost — no project, no keys.
  \item A single \texttt{run\_id} threaded through \texttt{RuntimeContext} + the \texttt{ObservabilityHook} span-per-stage gives end-to-end tracing from the audit trail.
  \item CI (\texttt{ci.yml}) runs the same two tiers; it is committed but disabled at GitHub level until an engineer enables it.
\end{itemize}
\end{takeaways}

\newpage

# Chapter 17 — CI/CD and the Coordinated Release

\index{CI/CD}\index{coordinated release}\index{Maven Central}\index{PyPI}

Culvert's GCP-only first iteration had a pleasantly simple
publishing model: tag, push, watch the GitHub Actions `publish-libraries.yml`
fire, and ten minutes later six new packages appeared on PyPI. I will not pretend
that wasn't convenient. But it came with a sting I only properly felt after the
third time a tag fired on a Tuesday morning before I had finished the
corresponding migration note. The publish was automatic, irreversible, and the
version number was gone.

Culvert does not do that. The publish is gated. Nothing goes to Maven Central or
PyPI without a deliberate, Joseph-triggered action. That isn't timidity — it is
the direct consequence of having two ecosystems that must land *together*. A Java
release without its Python counterpart, or the reverse, would leave the framework
in a state where half its surface is published and the other half is not. That is
not a state I want `com.enrichmeai.culvert` or `culvert` on PyPI to ever be in.

## The CI workflow

The gate is a single workflow file: `.github/workflows/ci.yml`\index{ci.yml},
written in Sprint 15 (T15.1 / #77) and extended by T15.2 (#79) and T15.3 (#83).
It covers a polyglot reactor: thirteen Java modules, three Python GCP adapter
modules, a Testcontainers emulator integration tier, and an E2E structural gate.

The file opens with an honest comment that is worth quoting directly
(`.github/workflows/ci.yml`:14--16):

```
# NOTE — workflow is intentionally NOT enabled at the GitHub level.
# Re-enabling (gh workflow enable / UI toggle) is an ENGINEER trigger once
# the team is ready to resume Actions minutes.
```

I wanted that in writing. The workflow is correct and tested; it is simply not
consuming Actions minutes on a project that has not yet published. When the
coordinated release is ready, one command re-enables it. Until then, it exists as
a contract with our future selves.

### Job 1 — verify-module-list

The first job does something I wish I had done years earlier
(`.github/workflows/ci.yml`:79--125). It diffs the workflow's explicit Java
module matrix against the `<modules>` block in
`data-pipeline-libraries-java/pom.xml`. If a new module is added to the reactor
but its name is missing from the CI matrix, the job fails loudly. A module gap in
a matrix is the worst kind of CI blind spot — everything passes, nothing is
actually tested, and you discover the omission six months later during a release.
This job makes the omission a visible red build, not a silent pass.

Thirteen modules are enumerated (`.github/workflows/ci.yml`:97--110):

```
data-pipeline-core-java
data-pipeline-gcp-secrets-java
data-pipeline-gcp-bigquery-java
data-pipeline-gcp-gcs-java
data-pipeline-gcp-pubsub-java
data-pipeline-gcp-observability-java
data-pipeline-gcp-dataflow-java
data-pipeline-tester-java
data-pipeline-it-support-java
data-pipeline-contract-tests-java
data-pipeline-aws-s3-java
data-pipeline-azure-blob-java
data-pipeline-orchestration-java
```

The AWS and Azure skeleton modules are in there. They are minimal — a proof that
the contract seam works across cloud targets — but they must compile and their
tests must pass like everyone else. There is no special treatment for "not fully
implemented yet."

### Job 2 — java-build matrix

Job 2 runs the full reactor in a fan-out matrix, one leg per module
(`.github/workflows/ci.yml`:133--182). Each leg uses `-pl <module> -am` so Maven
only builds the specific module and its inter-module dependencies — not the whole
reactor every time. The matrix is set with `fail-fast: false`
(`.github/workflows/ci.yml`:139), which means all thirteen legs report
independently. I find the default `fail-fast: true` maddening in multi-module
builds: one red module aborts the rest, and you go around again. With
`fail-fast: false` you get the complete picture in one run.

The Maven cache key is tied to a hash of all `pom.xml` files in the reactor
(`.github/workflows/ci.yml`:171):

```yaml
key: maven-${{ hashFiles('data-pipeline-libraries-java/**/pom.xml') }}
restore-keys: |
  maven-
```

The restore-key fallback (`maven-`) means a cold runner still benefits from any
prior cache entry. The first run is slow; subsequent runs are fast. The same key
and restore pattern is reused by the IT and E2E jobs so all three tiers share a
warm cache.

Surefire's defaults exclude `*IT.java` — integration tests stay out of this tier.

### Job 3 — python-tests

Three Python GCP adapter modules run in a parallel matrix
(`.github/workflows/ci.yml`:193--238):

- `data-pipeline-gcp-bigquery`
- `data-pipeline-gcp-gcs`
- `data-pipeline-gcp-pubsub`

The install order matters (`.github/workflows/ci.yml`:225--228): `data-pipeline-core`
goes in first as a local editable install, then the adapter. This is deliberate —
`data-pipeline-core` is not on PyPI yet, and we cannot let pip try to fetch it
from the index. Installing it locally in editable mode (`-e`) pins it to the
working tree.

`data-pipeline-orchestration` is excluded pending tech-debt #88: a test file
references an Airflow 3.x import path that does not exist under the pinned
Airflow 2.9.x. A `pytest.skip()` guard is in place, but the module cannot be
collected cleanly on a bare CI runner without Airflow installed. The fix is
tracked; the exclusion is documented at the top of the workflow file
(`.github/workflows/ci.yml`:29--38) rather than left as a silent gap.

### Job 4 — java-it (emulator ITs)

This tier was added in T15.2 (#79) and is the one I find most satisfying
(`.github/workflows/ci.yml`:267--303). It runs `mvn -P it verify` against
Testcontainers-backed emulators for BigQuery, GCS, and Pub/Sub — and it requires
zero GCP credentials. No service-account JSON. No project ID. The ITs use
localhost emulator ports; they never reach a real GCP endpoint. Docker is
available on `ubuntu-latest` runners without any `services:` block; Testcontainers
auto-detects it.

The IT job only runs after `java-build` is green (`.github/workflows/ci.yml`:270:
`needs: java-build`). Unit-test failures abort the IT tier. This is intentional:
there is no value in running emulator tests if the module doesn't compile.

The `it` profile is activated in `data-pipeline-libraries-java/pom.xml`
(lines 239--259) by `maven-failsafe-plugin`, which picks up `*IT.java` suffixed
classes that Surefire's default pattern ignores. The two profiles — `it` for
integration tests, `release` for publishing — are additive and independent:
`mvn -P it verify` and `mvn -P release deploy` are separate commands with
separate concerns.

### Job 5 — e2e-gate (T15.3 / #83)

The E2E gate compiles and runs the standalone reference deployment
`deployments/reference-e2e-gcp` on DirectRunner with in-memory recording hooks
(`.github/workflows/ci.yml`:327--371). No Docker. No live GCP credentials. The
deployment's `pom.xml` has no parent in the reactor — the Culvert library
artefacts at `com.enrichmeai.culvert:0.1.0` are not on Maven Central yet, so the
E2E job installs them into the local `~/.m2` first, then runs the deployment
tests. The step comment spells this out
(`.github/workflows/ci.yml`:351--353):

```yaml
- name: Install Culvert library artifacts into local Maven repo
  # The deployment is standalone (not in the reactor), so its dependencies
  # are not built as a side-effect of the reactor build.
```

One test is intentionally left disabled in the E2E suite — the live GCS
quarantine IT — because enabling it would require Docker inside this job. That is
flagged as the remaining open DoD box for the architect to verify.

### Job 6 — ci-gate

A single status-check job that collects all four required jobs
(`.github/workflows/ci.yml`:378--399):

```yaml
ci-gate:
  needs: [java-build, python-tests, java-it, e2e-gate]
  if: always()
```

The `if: always()` means the gate job runs even when upstream jobs fail — so it
can report exactly which leg caused the problem, rather than showing as "skipped"
on the PR status. Branch protection registers only `ci-gate` as the required
check. Add new jobs, wire them into `needs:` here, and the PR merge contract
updates automatically.

## The release model

The predecessor auto-published on tag push. Culvert does not. The reason is the
coordinated gate.

`docs/framework-evolution/13-python-parity-release.md` (lines 34--48) makes the
model explicit:

```
Java 0.1.0 (built, frozen)  ─┐
                             ├─►  coordinated 0.1.0  ──►  Maven Central + PyPI (culvert), together
Python parity (this epic)  ──┘
```

Java is at `0.1.0` — built, tagged `java-0.1.0`, frozen. It does not publish
on its own. The tag exists to prevent the Java side from silently drifting while
the Python parity work (Waves A through D) catches up. When Python is ready —
contracts reconciled, adapter parity achieved, distributions renamed to `culvert`
— both sides publish together, or neither does. The version number `0.1.0` will
appear on Maven Central and PyPI simultaneously. There will be no window where
`pip install culvert` fails because the Java artefacts are already out but the
Python wheel is not.

### The Maven side

The `release` profile in `data-pipeline-libraries-java/pom.xml` (lines 261--291)
is the mechanism:

```xml
<profile>
    <id>release</id>
    <build>
        <plugins>
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-gpg-plugin</artifactId>
                ...
                <!-- signs during the verify phase -->
            </plugin>
            <plugin>
                <groupId>org.sonatype.central</groupId>
                <artifactId>central-publishing-maven-plugin</artifactId>
                <version>0.5.0</version>
                <configuration>
                    <publishingServerId>central</publishingServerId>
                    <autoPublish>false</autoPublish>
                </configuration>
            </plugin>
        </plugins>
    </build>
</profile>
```

`autoPublish>false</autoPublish>` is the operative line. The
`central-publishing-maven-plugin` uploads the staged bundle to Sonatype's
Central Portal but holds it in the portal's review queue — it does not flip the
"publish" switch automatically. A human (me) has to log into
`central.sonatype.com`, inspect the staged bundle, and click Release. That is a
deliberate second gate after the Actions run.

The GPG passphrase, the Sonatype credentials, and the PyPI token are my secrets.
They are not in the repository. Dev-agents do not have them and cannot trigger a
release. This is not a process gap — it is the design.

### The Python side

PyPI trusted publishing (OIDC) is Wave D — the Actions publish job does not exist
yet (`docs/framework-evolution/13-python-parity-release.md`:79). When it lands,
the plan is OIDC / trusted publishing: the Actions job proves it is running on
the correct repository and branch by presenting an OIDC token; PyPI mints a
short-lived upload credential in response. No stored API token. No long-lived
secret to rotate.

The distribution name will be `culvert` (not `data-pipeline-*`), with import
shims from the old names kept for one release. The decision on whether to ship a
single `culvert` mega-package or `culvert` + `culvert-gcp-*` namespace
sub-packages is open — the recommendation is the split to keep install footprint
small and mirror the Maven module story, but Joseph decides before Wave D
(`docs/framework-evolution/13-python-parity-release.md`:148--152).

## Publishing and deploying are different things

The predecessor made this distinction clear, and Culvert inherits it. A library
publish creates a versioned artefact in a registry (Maven Central or PyPI); a
deployment runs infrastructure and pushes a Dataflow template. Conflating them
creates race conditions where a deployment consumes a published version that has
not yet propagated through the registry's CDN, and it creates an asymmetry where
a library fix requires a deploy cycle rather than a version bump.

The workflow file has no deploy steps. When Culvert's reference deployments
(`deployments/reference-e2e-gcp` and any future production deployments) need
their own Actions workflow, it will be a separate file. The `ci.yml` name is not
`ci-and-release.yml` for the same reason.

## Honest status

To be plain: nothing has been published.

`com.enrichmeai.culvert:*` does not exist on Maven Central. `culvert` does not
exist on PyPI. The `gcp-pipeline-*` packages — the predecessor — exist on PyPI
and will be deprecated-in-place when the coordinated release happens. They will
not be yanked in a way that breaks existing pinned installs.

The Java reactor builds and all unit tests pass. The Testcontainers IT tier
passes. The E2E gate passes on DirectRunner. The workflow file is correct. The
release profile in the POM is correct. What remains is Python parity (Waves C and
D), the Actions PyPI publish job, and the coordinated-release runbook in
`RELEASE.md` (Wave E).

The publish, when it happens, will be irreversible. PyPI version numbers cannot
be reused. Maven Central is immutable. That is exactly why the gate is human, not
automatic, and why it is mine to pull.

\begin{takeaways}
\textbf{Key takeaways}
\begin{itemize}
  \item The coordinated release model holds both ecosystems to a shared gate: Java \texttt{0.1.0} is built and frozen; it does not publish to Maven Central until Python parity (Wave D) is complete and both sides ship together.
  \item The CI workflow (\texttt{.github/workflows/ci.yml}) covers four tiers: a reactor module-list guard, a Java unit-test matrix, Python GCP adapter tests, and a Testcontainers emulator IT tier — all gated behind a single \texttt{ci-gate} required-status-check.
  \item The workflow is committed but intentionally disabled at the GitHub level until the team is ready to consume Actions minutes. One engineer command re-enables it.
  \item \texttt{autoPublish=false} in the Maven \texttt{release} profile means the Central Portal upload requires a manual review and release click — there is no automatic flip to production.
  \item PyPI publish will use OIDC trusted publishing (Wave D) — no stored API token, no long-lived secret. The GPG passphrase and all credentials remain Joseph-only.
  \item Publishing is irreversible. That is not a footnote; it is the architectural reason the gate is manual.
\end{itemize}
\end{takeaways}

\newpage

# Operating Culvert on GCP

Everything so far has been about the framework. This chapter is about *running its first implementation*. I want to be precise about the framing, because it matters to the whole thesis: GCP is Culvert's first cloud, not its only one. The operational specifics — the Terraform, the project layout, the choice of where to run the orchestrator — are properties of *the GCP implementation*, and they live here, in one place. Another cloud brings its own infrastructure-as-code and its own setup; the framework core does not change. Keeping the cloud-specific operations quarantined in one chapter is the same discipline that keeps `google.cloud` out of the contracts.

## Infrastructure as code

The GCP adapters need real resources: a GCS bucket for `GcsBlobStore`, BigQuery datasets for `BigQueryWarehouse` and the job-control ledger, Pub/Sub topics and subscriptions for the streaming source and sink, a Secret Manager secret for `SecretManagerProvider`, and the IAM to bind them to a service account. Provision these with Terraform, checked in and applied from CI — never by hand in the console, because hand-built infrastructure is infrastructure nobody can rebuild after an outage.

The rule I hold to: the Terraform mirrors the adapters. If you install `culvert-gcp-pubsub`, the Terraform that stands up its topics lives next to it. Adding an adapter and adding its infrastructure are the same change, reviewed together — the operational echo of the auto-config principle.

## Setting up the GCP environment

Before the Terraform runs, you need the substrate: a project (or a project per environment — dev, staging, prod, cleanly separated), the APIs enabled, a network, and a service account with least-privilege roles for exactly the resources the adapters touch. The engineer skill set is worth naming honestly, because it is broader than "writes Python": you need enough GCP IAM to reason about who can read a bucket, enough networking to place a private worker, and enough Terraform to review a plan. Culvert does not remove that requirement; it *contains* it — the cloud knowledge you need is bounded by the adapters you actually install.

## Where to run the orchestrator

Culvert's orchestration is cloud-neutral by design: a `DagSpec`/`TaskSpec` model plus renderers (Chapter [Orchestration]). *Where you run the rendered DAG* is a deployment choice, and on GCP you have two honest options:

- **Cloud Composer** — managed Airflow. The `ComposerDagRenderer` targets it. You pay for a standing environment; you get Google operating the scheduler. This is the right default for most teams: the operational overhead you avoid is worth more than the money you save self-hosting.
- **Self-hosted Airflow on GKE** — for teams that cannot use Composer for regulatory, hybrid-estate, or extreme-scale reasons. The `AirflowDagRenderer` produces standard DAGs that run on any Airflow, including one you operate on your own Kubernetes cluster. This is a real escape hatch, not the recommended path — running Airflow on Kubernetes is a standing operational commitment, and you should adopt it only when a constraint forces you off the managed option.

Because the DAG model is cloud-neutral and the renderer is swappable, that Composer-vs-GKE decision is reversible: it changes the renderer and the deployment target, not the pipeline.

## A word on cost

Everything here has a bill attached — a Composer environment, a GKE cluster, standing Pub/Sub, BigQuery slots. Put real numbers on it with the cost model (Appendix C) before you provision, not after the invoice. The single most expensive mistake I see is a pipeline that works and then costs twelve thousand dollars a month because nobody modelled it. Culvert gives you the `FinOpsSink` to measure it; use it from day one.

\begin{takeaways}
\textbf{Key takeaways}
\begin{itemize}
  \item GCP is Culvert's first implementation, not its only one; its operational specifics (Terraform, project setup, orchestrator placement) live in this one chapter, keeping the core cloud-neutral.
  \item Provision the resources the GCP adapters need with checked-in Terraform applied from CI; the infrastructure mirrors the installed adapters and is reviewed with them.
  \item Separate projects per environment, least-privilege service accounts, and a bounded-but-real GCP skill set (IAM, networking, Terraform) — Culvert contains the cloud knowledge you need, it does not abolish it.
  \item Orchestrator placement is a reversible deployment choice: Cloud Composer (managed, the default) via \texttt{ComposerDagRenderer}, or self-hosted Airflow on GKE (an escape hatch) via \texttt{AirflowDagRenderer}. Model the cost before provisioning.
\end{itemize}
\end{takeaways}

\newpage

# Chapter 18 — Cross-Cloud: The Adapter Seam

There is a specific kind of promise that framework authors make and then quietly stop
talking about. The promise is multi-cloud support. The quiet part is the small print:
*planned*, *roadmap*, *coming soon*. I have been on the receiving end of that small
print and I do not enjoy it.

So let me tell you exactly what exists today, why the design makes the rest possible,
and what "the rest" would actually cost to build. No small print.

## What the seam looks like

The `BlobStore` contract in
`data-pipeline-core-java/.../contracts/BlobStore.java`\index{BlobStore} is eight
methods: `get`, `openInput`, `openOutput`, `put`, `list`, `exists`, `delete`, and
`copy`. The contract's Javadoc says what every implementor must provide; it says
nothing about clouds.

```java
public interface BlobStore {
    byte[] get(String uri);
    InputStream openInput(String uri);
    OutputStream openOutput(String uri);
    void put(String uri, byte[] data);
    Iterator<String> list(String prefix);
    boolean exists(String uri);
    void delete(String uri);
    void copy(String src, String dst);
}
```

URIs are opaque strings — `gs://`, `s3://`, `abfs://`. The framework never parses
them. Implementations do. That single design decision is why a new cloud is a new
module rather than a new version of the framework.

The GCP implementation lives in
`data-pipeline-gcp-gcs-java/.../gcp/gcs/GcsBlobStore.java`. It accepts `gs://`
URIs, wraps the Google Cloud Storage client, and is production-tested. If you have
run a GCS pipeline against Culvert, this class is what did the byte-moving.

The AWS implementation lives in
`data-pipeline-aws-s3-java/.../aws/s3/S3BlobStore.java`. It accepts `s3://` URIs
and wraps `S3Client` from the AWS SDK v2. As of Sprint 21 (epic #144) it implements
all eight `BlobStore` methods, not a subset — more on that below. The Azure
implementation lives in
`data-pipeline-azure-blob-java/.../azure/blob/AzureBlobStore.java`. It accepts
`abfs://container@account.dfs.core.windows.net/path` URIs and wraps
`BlobServiceClient` from the Azure SDK. It is still a Sprint-8 skeleton: `exists()`
works, the other seven methods throw `UnsupportedOperationException`. Both classes
compile and pass their unit tests; only one of them is honestly describable as
"incomplete" any more.

## AWS: from one method to a real family

Let me be specific, because this is the point where framework authors tend to go
vague.

Through Sprint 8, `S3BlobStore`\index{S3BlobStore} implemented `exists()` and
nothing else — the other seven methods threw `UnsupportedOperationException`. That
was true when the first edition of this chapter was written. It is not true any
more. Sprint 21 (epic #144) closed that gap: `S3BlobStore` now implements `get`,
`openInput`, `openOutput`, `put`, `list`, `delete`, and `copy` alongside the
original `exists()` — all eight `BlobStore` methods, unit-tested and exercised
against a real S3 API surface via a LocalStack integration test
(`S3BlobStoreLocalStackIT`). The one deliberate simplification worth knowing about:
`openOutput()` buffers the write in memory and issues a single `PutObject` call on
close, rather than driving S3's multipart-upload protocol — the right tradeoff for
config, manifests, and small extracts, and documented in the class Javadoc as a
follow-up seam if multi-gigabyte streaming writes ever show up.

`BlobStore` was not the only contract that moved. The same sprint added three more
real AWS adapters:

- `AwsSecretsManagerProvider` (`data-pipeline-aws-secrets-java`) implements
  `SecretProvider` against AWS Secrets Manager, mapping the contract's `"latest"`
  version onto AWS's `AWSCURRENT` version stage — AWS has no `"latest"` alias the
  way GCP Secret Manager does, so the adapter translates the concept rather than
  assuming it.
- `SqsSource` and `SqsSink` (`data-pipeline-aws-sqs-java`) implement `Source` and
  `Sink` against an SQS queue, mirroring `PubSubSource`/`PubSubSink`'s shape but
  documenting where SQS's semantics genuinely differ — eager-delete-on-read makes
  `SqsSource` at-most-once by design, and `SqsSink` batches at SQS's own
  ten-message `sendMessageBatch` ceiling, surfacing partial-batch failures as a
  `SqsPublishException` rather than swallowing them.
- `DynamoDbJobControlRepository` (`data-pipeline-aws-dynamodb-java`) implements
  `JobControlRepository` against DynamoDB, and it is worth dwelling on because it
  is not just a port — it is a genuine improvement over what BigQuery offers. More
  on that below.

`AzureBlobStore` is unchanged: `exists()` works, the rest throw. It is still exactly
the Sprint-8 proof-of-concept the first edition of this chapter described: a
skeleton that proves the seam takes the plug, not a production adapter.

## The DynamoDB control plane: better than BigQuery, not just different

`BigQueryJobControlRepository` implements every status transition — `markFailed`,
`updateStatus`, and friends — as a plain `UPDATE ... WHERE run_id = @run_id`
statement. BigQuery has no compare-and-swap primitive. Two concurrent callers
racing to, say, mark the same run both failed and succeeded can both "succeed" —
the last writer wins silently, and neither caller finds out it lost the race.

DynamoDB's `PutItem` and `UpdateItem` APIs accept a `ConditionExpression` that is
evaluated atomically against the server-side item state as part of the same
request: the write either commits or is rejected with
`ConditionalCheckFailedException`, with no window for a concurrent writer to
interleave. `DynamoDbJobControlRepository` uses exactly that — conditional writes
as the concurrency primitive for status transitions. That is a genuine
transactional control plane that the BigQuery implementation structurally cannot
offer without adding a lock table or an optimistic-concurrency column of its own.
It is the reason DynamoDB is in the AWS family at all, not just a box-ticking
"cover `JobControlRepository` too."

I want to be precise about what this does and does not mean. It does not mean AWS's
`JobControlRepository` is "ahead" of GCP's in the way a feature-completeness
scoreboard would suggest — the BigQuery adapter has years of production traffic
behind it, and DynamoDB's is new. It means the *contract* exposed a real
architectural difference between the two backends, and the difference resolved in
DynamoDB's favour for this one property. That is exactly what a contract-driven
design is supposed to surface.

## The same pipeline, two clouds

The claim this chapter has been building towards is now executable. The
ingestion deployment's launcher takes a `--cloud` flag: `gcp` (the default)
wires `GcsBlobStore` + `BigQueryWarehouse` + `BigQueryJobControlRepository`;
`--cloud=aws` wires `S3BlobStore` + `AthenaWarehouse` +
`DynamoDbJobControlRepository`. The `IngestionStage` and `IngestionRunner`
underneath — envelope parse, validate, stage, load, quarantine, reconcile,
job control — are byte-identical on both paths. Swapping clouds changes which
constructors run in `main()`. Nothing else.

And that is not a diagram claim; it is a test.
`CrossCloudIngestionLocalStackIT` runs the *same* `IngestionRunner` the GCP
deployment uses against a **real** S3 API and a **real** DynamoDB (LocalStack):
the HDR/TRL source file is seeded through `S3BlobStore` itself, the staged
NDJSON really lands in an S3 bucket, and the job-control transitions — with
DynamoDB's conditional writes enforcing them atomically — are read back
through the same repository that wrote them. The `Warehouse` leg uses a
recording stand-in there, because community LocalStack has no Athena; the
Athena load path itself (a run-scoped external table over the staging prefix,
a typed `INSERT INTO ... SELECT`, a `COUNT(*)`, and a best-effort `DROP` —
suffix-driven between OpenCSVSerde for CSV and JsonSerDe for the runner's
NDJSON staging files, mirroring the pilot's format detection) is covered by
its own mocked-client suite, with real-AWS validation reserved for the cloud
deploy phase. I am not going to blur those two confidence levels — but the
architectural claim, *same pipeline, adapter swap*, runs green on both clouds
today.

Also explicitly out of scope for Sprint 21, and worth stating plainly rather than
letting it be assumed: an AWS execution layer. Apache Beam is runner-portable by
design — the same `Pipeline`/`PipelineStage` graph that targets Dataflow can in
principle target a different Beam runner — so there is no `data-pipeline-aws-emr`
or `data-pipeline-aws-flink` module and no immediate plan for one. An
EMR-or-Flink-as-the-Dataflow-equivalent runner story is a future consideration, not
a current gap in "the AWS family," because it was never this sprint's job. And
Python parity for any of this — an AWS family in the Python library set — is
explicitly deferred past the 0.1.0 release; see
`docs/framework-evolution/13-python-parity-release.md`.

## The full contract set

`BlobStore` is one of sixteen contracts in
`data-pipeline-core-java/.../contracts/`\index{contracts!full set}. The other
fifteen are:

`Source`, `Sink`, `Transform`, `Pipeline`, `PipelineStage`, `RuntimeContext`,
`JobControlRepository`, `AuditEventPublisher`, `FinOpsSink`, `GovernancePolicy`,
`LineageEmitter`, `ObservabilityHook`, `SecretProvider`, `StageMetricsHook`, and
`Warehouse`. (There is also `StageMetrics`, which is a value type carried through the
pipeline, not an adapter contract — the seam is sixteen.)

AWS now implements eight of those sixteen: `BlobStore` (S3), `SecretProvider`
(Secrets Manager), `Source` and `Sink` (SQS), `JobControlRepository`
(DynamoDB), `Warehouse` (Athena, including the external-table load path), and
`ObservabilityHook` + `StageMetricsHook` (CloudWatch, same metric names and
label schema as the GCP hooks). Azure implements one:
`BlobStore`, and at one of its eight methods. The GCP family covers the
cloud-specific seams in full: six adapter modules implementing `BlobStore` (GCS),
`Warehouse` + `AuditEventPublisher` + `FinOpsSink` + `JobControlRepository`
(BigQuery), `Source` + `Sink` for streaming (Pub/Sub), `SecretProvider` (Secret
Manager), `ObservabilityHook` + `StageMetricsHook` + `LineageEmitter` (Cloud
Monitoring, Cloud Trace, Data Catalog), and the Beam execution layer (Dataflow).
The contracts that are cloud-neutral by design — `GovernancePolicy`,
`RuntimeContext`, and the no-op defaults — are implemented in core itself
(`data-pipeline-core-java/.../finops/BudgetGovernancePolicy.java`,
`.../runtime/NoOpDefaults.java`), not in a cloud-specific module.

That is the gap stated plainly: the cloud-specific contracts have a full GCP
family; AWS has a real, growing family that is not yet complete (five of sixteen,
soon eight, still short of an execution layer and of `AuditEventPublisher`,
`FinOpsSink`, and `LineageEmitter`); Azure still has a single skeleton covering
`BlobStore` only.

## The Spring move, explained without nostalgia

I keep reaching for the Spring comparison\index{Spring Framework} and I am going to
keep reaching for it because I have not found a better one.

`spring-data-jpa` shipped first. It was the only persistence module for years. When
`spring-data-mongodb` eventually arrived — written largely by the MongoDB team itself —
the JPA users did not need to learn a single new concept. The contracts that
`spring-data` had defined were honest enough that MongoDB could plug into them
without contorting itself or contorting the users' existing code. The contracts were
designed for *persistence in general*, not for relational databases specifically, even
when only one persistence family existed.

That is the move here. The `BlobStore` interface does not mention buckets or blob
containers or S3's eventual consistency model or Azure's hierarchical namespace. It
mentions bytes and URIs and eight operations that any object store you have ever used
would recognise. The BigQuery-specific optimisations — clustering, partitioning,
slot-aware cost predicates — live in
`data-pipeline-gcp-bigquery-java/.../BigQueryWarehouse.java` and are not in
`Warehouse`\index{Warehouse}. The `Warehouse` contract covers the lowest common
denominator that any serious data warehouse supports, and nothing more — and that
same discipline is what the `AthenaWarehouse` adapter is held to.

The non-goal is a lowest-common-denominator warehouse. If you need BigQuery's
materialised views or partition pruning, you call `BigQueryWarehouse` directly and
call its BigQuery-specific extensions directly. The framework does not paper over that
with a `MaterializedViewAware` superinterface. It gives you the generic seam for the
generic work and steps aside for the specific work.

## What closing the rest of the AWS gap took — and what closing Azure's would take

Sprint 21 is a useful data point against the estimate the first edition of this
chapter made, so let me update the estimate with the actual experience rather than
just restating the old guess.

The old estimate was: seven more `BlobStore` methods on `S3BlobStore`, "a week's
work — mostly the streaming variants, the list iterator, and a careful mapping of
SDK exceptions into the framework's error taxonomy." That is what shipped. The
contract test in
`data-pipeline-contract-tests-java/.../BlobStoreContractTest.java` — five
behavioural checks (round-trip get, `exists` true/false, idempotent delete, null
rejection) — is what `S3BlobStore` now passes via a LocalStack-backed
implementation, the same specification the GCP `GcsBlobStore` passes in CI.

`SecretProvider` against AWS Secrets Manager was estimated at "probably two days,
a thin wrapper around the AWS SDK." That is also roughly what it took, with one
wrinkle the estimate did not anticipate: AWS has no `"latest"` version alias, so
the adapter had to design a mapping (`"latest"` → the `AWSCURRENT` version stage)
rather than simply forward a string. Contract-driven design earns its keep exactly
in moments like this — the contract says `"latest"` must mean something, and the
adapter has to figure out what that means on a backend that models versioning
differently.

`JobControlRepository` against DynamoDB was flagged as "architectural, not
mechanical," needing a schema and query patterns mapping the job ledger onto
DynamoDB's key-value model rather than BigQuery's SQL model. That held up, and
then some — the conditional-write control plane described above is the
architectural payoff the estimate anticipated, delivered as a genuine improvement
rather than a like-for-like port.

What is left for a *complete* AWS family: real-AWS validation of the Athena leg (mock-tested today — no community LocalStack), `AuditEventPublisher` and `FinOpsSink` (not yet started; likely SNS/SQS and an
S3 `put` respectively, similarly scoped to what shipped this sprint), and an
execution adapter — Beam on EMR or an equivalent runner — which remains the
heaviest piece and is explicitly out of scope for this block. A complete AWS
family including that execution layer and real-AWS CI is still a multi-month
build; the difference from the first edition of this chapter is that "a complete
AWS family" no longer means starting from `exists()` — it means finishing three or
four more contracts plus the execution layer, with the storage, secrets, streaming,
and job-control tier already real and tested.

Azure has had no equivalent investment this sprint and the estimate for it is
unchanged: the most complicated piece would be `AzureBlobStore`'s URI convention
— the ABFS scheme (`abfs://container@account.dfs.core.windows.net/path`) that
`AzureBlobStore.java` already parses — and mapping Azure Data Lake Storage Gen2's
namespace semantics onto the `list` and `copy` methods. Synapse as a `Warehouse`
implementation has subtler divergences from BigQuery's SQL semantics than Athena
or Redshift do, so the `WarehouseContractTest` may expose a protocol revision.
Not impossible, just non-trivial, and nobody has started.

## What "enabled, not promised" means in practice

AWS's family and Azure's skeleton are both *enabled by the design*; only AWS has
also been *built*, this sprint, by this team. Those are three different states —
enabled, built, and published — and it matters to keep them distinct.

"Enabled" means the contracts are honest, the naming convention reserves the module
slots, the contract test harness will validate any adapter against the same
behavioural specification the GCP adapters pass today, and the `AutoConfig` registry
discovers installed adapters at boot via Java's `ServiceLoader` —
`data-pipeline-core-java/.../autoconfig/AutoConfig.java` loads every
`META-INF/services/com.enrichmeai.culvert.contracts.*` entry it finds on the
classpath. That is how `S3BlobStore`, `AwsSecretsManagerProvider`, `SqsSource`,
`SqsSink`, and `DynamoDbJobControlRepository` all get picked up at runtime without
any core changes — the same mechanism Azure's `AzureBlobStore` uses today, and the
same mechanism a future `AthenaWarehouse` or `CloudWatchMetricsHook` will use once
they land.

"Built" is what actually happened for AWS in Sprint 21: five real contracts,
unit- and LocalStack-tested, not hypothetical. "Promised" would mean I have
committed to a ship date for the *rest* of the AWS family, or for Azure, and a team
is working toward it on a calendar. That is still not true. Culvert is built and
held at version 0.1.0. Nothing is published to Maven Central. The AWS family that
exists is real, but it is not complete, and Azure's skeleton exists in the
repository to validate the seam, not to promise a release.

I have watched other vendors make the rhetorical drift from "the contracts allow
multi-cloud" to "we are a multi-cloud framework". The gap between those two
sentences is the gap that burns customers. I am not going to smudge over it. If
your procurement team asks whether Culvert runs on AWS today: for blob storage,
secrets, SQS-based streaming, and transactional job control, yes, and it is
tested against LocalStack, not just compiled. For a data warehouse, for
observability, for an execution engine, not yet. If they ask about Azure, the
answer is still no beyond `exists()` on a blob path.

## The contract tests as the handshake

The contract test module —
`data-pipeline-contract-tests-java/.../contracttests/BlobStoreContractTest.java` — is
the mechanism that makes the seam real rather than rhetorical. It is abstract. It
declares three abstract methods: `store()`, `knownUri()`, and `missingUri()`. Any
`BlobStore` implementor extends it, provides a real store backed by their cloud or a
localstack equivalent, and gets five behavioural tests for free.

`S3BlobStore` is no longer a hypothetical "future AWS implementor" in this
section — it is a real extender of `BlobStoreContractTest`, backed by a LocalStack
container, running the same specification the GCP `GcsBlobStore` passes in CI
today. The abstraction held: no leak surfaced that required revising the
`BlobStore` contract itself to accommodate S3's shape. `SqsSource`/`SqsSink` and
`AwsSecretsManagerProvider` follow the same handshake pattern against their own
contract test bases.

`DynamoDbJobControlRepository` has its own LocalStack integration suite
(`DynamoDbJobControlLocalStackIT`) proving the conditional-write guarantees
against real DynamoDB semantics — duplicate creates and transitions-on-missing
are rejected atomically, not just in a mock's imagination.
`AthenaWarehouseContractTest` and `AwsSecretManagerContractTest` bind the shared
`WarehouseContractTest`/`SecretProviderContractTest` suites the same
extend-provide-run way.

## The honest summary

AWS is no longer "one skeleton class." It is a real adapter family covering eight
of sixteen contracts — `BlobStore` (S3, all eight methods), `SecretProvider`
(Secrets Manager), `Source`/`Sink` (SQS), `JobControlRepository` (DynamoDB,
with a transactional control plane BigQuery cannot structurally match),
`Warehouse` (Athena, including the external-table load path), and
`ObservabilityHook`/`StageMetricsHook` (CloudWatch) — built, unit-tested, and
LocalStack-integration-tested where community LocalStack reaches (S3, SQS,
Secrets Manager, DynamoDB, CloudWatch); Athena is mock-tested only, for the
honest reason that no community LocalStack Athena exists to validate against,
and its real-AWS validation is reserved for the cloud deploy phase. The same
ingestion pipeline runs on both clouds via an adapter swap, and a LocalStack
integration test proves it. An AWS execution layer and Python-side AWS parity
are explicitly out of scope for this block.

Azure is exactly where it was: a single skeleton class, one of eight `BlobStore`
methods implemented, proof that the seam compiles against a non-GCP cloud and
nothing more.

Sixteen contracts exist in core. The cloud-specific ones — `BlobStore`, `Warehouse`,
`JobControlRepository`, `AuditEventPublisher`, `FinOpsSink`, `LineageEmitter`,
`ObservabilityHook`, `StageMetricsHook`, `SecretProvider`, `Source`, `Sink` — have
GCP adapters across six modules, the only family that runs production pipelines.
AWS now has real adapters for five of those eleven cloud-specific contracts
(soon seven), Azure for one. The cloud-neutral ones (`GovernancePolicy`,
`RuntimeContext`) have core-module implementations that work without any cloud at
all, on any backend.

That is the current state. The design made the AWS work additive rather than
reconstructive, and Sprint 21 is the evidence: the estimate this chapter made in
its first edition — days for `SecretProvider`, a week for the remaining `BlobStore`
methods, "architectural, not mechanical" for `JobControlRepository` — held up
against what actually got built. The contract tests made the work verifiable
against the same specification the GCP adapters already pass. The naming
convention reserved the module slots long before anyone wrote code into them.

Unlike the first edition's framing, this was not a case of waiting for an outside
team to want AWS badly enough to build it — this team built it, in-house, this
sprint, because the client work needed it. Azure is still the piece nobody has
needed badly enough to build past the skeleton, and that framing — "enabled, not
yet built, because nobody has needed it enough" — is now Azure's story specifically,
not AWS's and Azure's story together.

The seam is real. Half the family is now real too, for AWS specifically. The rest
of the family — for AWS and for Azure both — is not yet. All three of those
sentences are true and none of them cancels the others.

\begin{takeaways}
\textbf{Key takeaways}
\begin{itemize}
  \item \textbf{AWS moved from one skeleton method to a real adapter family in
        Sprint 21 (epic \#144):} \texttt{S3BlobStore} implements all eight
        \texttt{BlobStore} methods (\texttt{data-pipeline-aws-s3-java});
        \texttt{AwsSecretsManagerProvider} implements \texttt{SecretProvider}
        against Secrets Manager; \texttt{SqsSource}/\texttt{SqsSink} implement
        \texttt{Source}/\texttt{Sink} against SQS; \texttt{DynamoDbJobControlRepository}
        implements \texttt{JobControlRepository} with a transactional,
        conditional-write control plane that BigQuery's plain-UPDATE approach
        cannot structurally match. Five of sixteen contracts, unit-tested and
        partially LocalStack-IT-tested.
  \item \textbf{Azure is unchanged}: \texttt{AzureBlobStore}
        (\texttt{data-pipeline-azure-blob-java}) still implements only
        \texttt{BlobStore.exists()}; the remaining seven methods throw
        \texttt{UnsupportedOperationException}. It remains proof that the seam
        compiles across clouds, not a production adapter.
  \item \textbf{The same pipeline runs on both clouds} — the ingestion
        launcher's \texttt{--cloud} flag swaps the adapter family
        (GCS/BigQuery vs S3/Athena/DynamoDB) under a byte-identical
        \texttt{IngestionRunner}, and \texttt{CrossCloudIngestionLocalStackIT}
        proves the AWS path against real S3 and real DynamoDB. The one honest
        caveat: the Athena leg is mock-tested (no community LocalStack Athena);
        its real-AWS validation lands with the cloud deploy phase. An AWS
        execution layer (Beam on EMR/Flink) and Python-side AWS parity are
        explicitly out of scope for this block; \textbf{Azure is explicitly
        later}.
  \item There are \textbf{sixteen contracts} in
        \texttt{data-pipeline-core-java/.../contracts/}. The cloud-specific seams
        have a full GCP family across six modules. AWS now covers eight of
        sixteen; Azure covers one, at one of eight methods. The cloud-neutral
        contracts (\texttt{GovernancePolicy}, \texttt{RuntimeContext}) have core
        implementations that work on any cloud.
  \item The AWS build \textbf{validated the first edition's estimates}:
        days for \texttt{SecretProvider}, about a week for the remaining
        \texttt{BlobStore} methods, "architectural, not mechanical" for
        DynamoDB's \texttt{JobControlRepository}. The contract test harness
        (\texttt{BlobStoreContractTest}, \texttt{WarehouseContractTest},
        \texttt{SecretProviderContractTest}) validated the new adapters against
        the same behavioural specification the GCP adapters pass today.
  \item \textbf{Enabled, built, and published are three different states.}
        \texttt{AutoConfig} discovers installed adapters at boot via Java
        \texttt{ServiceLoader} — register an impl under
        \texttt{META-INF/services/} and the runtime picks it up. AWS is now
        both enabled and built for five contracts. Azure is enabled but not
        built beyond the skeleton. Neither is published: no Maven Central
        release exists, and version 0.1.0 is built and held.
  \item The Spring precedent still holds, with one update: this AWS family was
        built in-house because the work needed it, not by an outside team
        that wanted it badly enough. Azure is still waiting for that team.
        Tourist adapters are worse than no adapters; the AWS family shipped
        this sprint was not a tourist adapter.
\end{itemize}
\end{takeaways}

\newpage

# Chapter 19 — An Honest Code Review

Throughout this book I have woven a "what works, what could be better" thread into each chapter. Now I want to pull those observations together and apply the oldest device in the engineer's toolkit: a frank self-review. Not a modesty performance, not a sales pitch. Something closer to what a good code review actually is — one person reading another's work with genuine curiosity and genuine willingness to say what they see.

The subject is Culvert at version 0.1.0. That version is real and sat on a branch labelled **built and held, not yet published** throughout the writing of this book. Every API, every module, every line number cited below is grounded in the actual source tree. I will not soften things that are genuinely incomplete, and I will not pretend things that are genuinely good are only adequate. Let us begin.

---

## What Culvert gets very right

**The contract seam.** The single decision that makes everything else possible: every cloud-specific capability lives behind a language-neutral interface. The `Warehouse` interface in `data-pipeline-core-java` is eleven lines and six methods; it carries no GCP, AWS, or Snowflake import (`Warehouse.java:24`). `BigQueryWarehouse` is a 391-line implementation of that interface (`BigQueryWarehouse.java:73`). When I later added `S3BlobStore` and `AzureBlobStore`, nothing in the framework code changed — only a new implementing class appeared. That is the Spring precedent in action: a design that forces a seam before you know what you will connect to later.

**Binary TiB in the FinOps constants.** A small thing that matters. The cost trackers define `BYTES_PER_TIB = 1_099_511_627_776L` — that is 2^40, the correct tebibyte (`BigQueryCostTracker.java:81`). The Python mirror confirms it: `BYTES_PER_TIB: int = 1_099_511_627_776  # 2^40` (`data-pipeline-gcp-bigquery/src/data_pipeline_gcp_bigquery/cost_tracker.py:40`). Google bills per TiB, and Google uses the binary definition. Rounding to the nearest terrabyte (10^12) underestimates charges by about 10%. That error makes budget alerts wrong, makes FinOps attribution wrong, and erodes trust in every cost report downstream. Getting this right from the first sprint saved work later.

**Contract tests as a shared safety net.** `WarehouseContractTest` in `data-pipeline-contract-tests-java` is an abstract JUnit class; `BigQueryWarehouseContractTest` extends it and plugs in a mock client. Every inherited test — `queryStreamsRows`, `tableExistsTrueForKnown`, `tableExistsFalseForMissing`, `nullSqlRejected` — runs against `BigQueryWarehouse` without any GCP credentials or network (`BigQueryWarehouseContractTest.java:45-101`). The Python mirror in `data-pipeline-contract-tests` defines the same four behaviours as a mixin (`warehouse.py:22-36`). This means that when a new adapter appears for a different warehouse, the author inherits forty years of learned wisdom about what "correct" looks like, expressed as assertions. It also means that the null/edge-case guards in `BigQueryWarehouse.streamRows` (null result handled at line 251, null schema at line 255) are *pinned* by tests rather than commented suggestions. A comment can drift; a failing test cannot.

**The deliberately conservative `Warehouse` contract.** The Javadoc is honest about the scope: "only the operations every serious warehouse supports". Cloud-specific operations — BigQuery slot-aware predicates, Redshift sort keys, Snowflake clustering — belong in a cloud extension class, not in the contract (`Warehouse.java:10-17`). This is easier to say than to enforce. Many framework authors tell themselves they are being conservative, then discover one day that they have a `setBigQueryPartitionDecoratorForLoadJob` method on their supposedly neutral interface. The escape hatch — `BigQueryExtensions` in the cloud module — keeps the contract clean and the extension surface honest.

**All 16 contracts backed, at least once, in Java.** The completion table in `CHANGELOG.md:22-41` shows every contract from `Source` to `SecretProvider` with at least one concrete adapter. The Java reactor stood at 13 modules, 478 tests, 0 failures, 0 errors at the point of the 0.1.0 freeze. That matters not because "478 tests" is an impressive number, but because it is evidence that the contracts are implementable, that the adapters compile, and that the mock-backed and emulator-backed tests agree on what the contracts mean.

---

## What I would change first

**`BigQueryWarehouse.merge()` is not implemented.** This is the most significant functional gap and I want to be precise about what it is: five of the six `Warehouse` methods are implemented and tested; `merge()` throws `UnsupportedOperationException` with a detailed comment explaining why (`BigQueryWarehouse.java:150-168`). The reason is real: BigQuery's `MERGE` syntax requires an explicit non-key column list in `WHEN MATCHED THEN UPDATE SET ...`; `SET t.* = s.*` is not valid SQL in BigQuery. Generating that column list requires a schema lookup against the source table before the MERGE can be constructed, which is non-trivial. Rather than ship a silently incorrect implementation, the decision was to defer and surface it loudly. That is the right call for a 0.1.x release. But callers will hit it, and "use `execute()` with an explicit MERGE statement" is a real workaround, not a full answer. This is the first thing to fix in a 0.2.0.

**AutoConfig cannot supply constructor arguments.** `AutoConfig.discover()` uses Java `ServiceLoader` to find adapters on the classpath (`AutoConfig.java:96-98`). `ServiceLoader` requires a public no-arg constructor. `BigQueryWarehouse` requires a `BigQuery` client and a project ID; it has no no-arg constructor, and the Javadoc says so explicitly (`BigQueryWarehouse.java:44-57`). The `META-INF/services` entry is pre-registered as a reservation for a future sprint, but today `AutoConfig.warehouse()` will return `Optional.empty()` on any classpath that contains only the sprint-1 adapters (`AutoConfig.java:220-233`). The `Throwable` swallow is especially uncomfortable: `ServiceConfigurationError` from a missing no-arg constructor is silently discarded with a comment marking it a "sprint-4 limitation". Python's entry-points mechanism has a similar problem (`data-pipeline-core/src/data_pipeline_core/runtime.py:17-30`), though the asymmetry runs the other way — Python `AutoConfig.discover()` yields *classes*, not instances, which then require constructor arguments that are unavailable worker-side. Neither half of the polyglot pair currently delivers the "just add a JAR / just `pip install`" experience that the auto-config chapter promises. That experience is the goal; right now it requires manual wiring.

**The Python `DefaultRuntimeContext` does not rebuild its registry across the serialisation boundary.** When a `RuntimeContextImpl` is serialised to a worker process (for a Beam or Dataflow job), only `run_id`, `environment`, and `config` cross the boundary — the `_registry` dict is excluded from `__getstate__` (`runtime.py:366-384`). In Java, worker-side rebuild happens automatically via `AutoConfig.discover()`. In Python it does not, because `AutoConfig.discover()` yields classes that need constructor arguments not available on the worker (`runtime.py:17-30`). The module docstring flags this explicitly as a "deliberate divergence" per the T18.1 DoD. Deliberate or not, it means that any Python pipeline stage that reads from `ctx.secrets` or `ctx.observability` after deserialisation will find an empty registry and raise a `RuntimeError`. There is no distributed Python execution in the framework yet, so this is currently latent. It will surface the first time someone tries it.

---

## What I would change next

**The AWS and Azure modules are proof-of-concept, not production adapters.** This deserves to be said plainly, because the `CHANGELOG.md:22-41` completion table lists `S3BlobStore` and `AzureBlobStore` next to `GcsBlobStore` under the `BlobStore` row, which reads as if all three are equivalent. They are not. `S3BlobStore` implements `exists()` and throws `UnsupportedOperationException` for the other seven methods (`S3BlobStore.java:59-98`). `AzureBlobStore` is the same (`AzureBlobStore.java:52-60`). One of eight `BlobStore` methods implemented is the right description. These modules exist to prove the contract compiles against non-GCP SDKs and that the adapter pattern extends beyond GCP. That proof is valuable. But callers must not discover the gap at runtime.

**The cross-language docstring coupling is a maintenance liability.** `runtime.py`'s docstrings contain references like "Mirrors Java `DefaultRuntimeContext` (:251–289)". These line numbers will rot the next time the Java file is edited. The intent is good — cross-language traceability is real engineering value — but hard-coded line references are the wrong carrier. An architectural decision record or a shared conformance note would age better.

**A cost-gate alert is one SQL query away.** The FinOps data is in `BigQueryFinOpsSink`. The `BYTES_PER_TIB` constant is correct. The cost-per-TiB rate is in `BigQueryCostTracker.QUERY_COST_USD_PER_TIB`. There is no scheduled alert that fires when any entity crosses a budget threshold. Everything needed for it exists; the wiring does not.

---

## What I would not change

A code review is not complete without this section. There are things that look like targets for "improvement" but are, in my judgement, correct as they stand.

**The deliberately unimplemented no-arg constructor.** The comment at `BigQueryWarehouse.java:94-99` explains why there is no no-arg constructor: a `BigQuery` client is not derivable from a small bag of environment variables within the "no-arg only if ≤2 env vars" rule. This is the right boundary. Adding a magical no-arg constructor that guesses credentials and project from the environment would work in some contexts and fail silently in others. The explicitness is a feature.

**The single-version coordinated release.** All 13 Java modules share the same version string, held in one place. The Python libraries share a `pyproject.toml`-level version. The release gate requires both sides to be ready before either publishes. This is unfashionable — the fashionable alternative is independent semantic versioning per module, with the attendant diamond-dependency chases that follow. The single-version discipline is harder to maintain and much easier to reason about.

**The conservative `Warehouse` contract surface.** I said this above as a strength; I say it again here as a design decision worth defending. When someone argues that `merge()` should be optional, or that the contract should expose partition decorators, the correct response is that cloud-specific operations belong in cloud extension classes. The contract being incomplete for one cloud is a gap to be filled. The contract picking up cloud-specific methods is a category error that can never be undone without breaking every existing adapter.

---

## A reading path for new contributors

If you are coming to this codebase fresh, the order I would recommend:

1. `data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/` — the 16 interfaces and `StageMetrics`. Forty minutes here prevents forty hours of confusion later.
2. `data-pipeline-core-java/.../autoconfig/AutoConfig.java` — how adapters are discovered and its current limitation.
3. `data-pipeline-gcp-bigquery-java/.../BigQueryWarehouse.java` — the most complete adapter, including the one honest `UnsupportedOperationException`.
4. `data-pipeline-contract-tests-java/.../WarehouseContractTest.java` and `BigQueryWarehouseContractTest.java` — the contract test pattern and how to extend it.
5. `data-pipeline-core/src/data_pipeline_core/runtime.py` — the Python side of the runtime context, including the serialisation note.
6. `CHANGELOG.md` — the sprint-by-sprint history, which is more honest about what is built versus what is claimed than most changelogs.

In that order you will see the seam, the discovery mechanism, the most complete implementation, the test harness, the Python partner, and the honest status report. By the end you will know enough to add a new adapter and know exactly what it means for it to be "done".

---

\begin{takeaways}
\textbf{Key takeaways}
\begin{itemize}
  \item Culvert 0.1.0 is built and held, not published. All 16 contracts have at least one Java adapter; 478 tests pass with 0 failures. That is the bar for calling something feature-complete.
  \item The contract seam — cloud-specific SDKs hidden entirely behind language-neutral interfaces — is the design decision that makes every other decision reversible.
  \item The two most significant gaps are both structural, not cosmetic: \texttt{BigQueryWarehouse.merge()} is deferred (sprint-4 scope, line 164); and \texttt{AutoConfig} cannot supply constructor arguments to adapters that need them (line 220--233), which means the promised zero-wiring discovery experience does not yet exist.
  \item The AWS S3 and Azure Blob adapters implement one of eight \texttt{BlobStore} methods each. The completion table in the changelog does not say this loudly enough. Know it before you promise a customer multi-cloud support.
  \item Things that look like candidates for change but are correct: the absence of a no-arg constructor in \texttt{BigQueryWarehouse}; the coordinated single-version release; the deliberately narrow \texttt{Warehouse} contract surface.
\end{itemize}
\end{takeaways}

\newpage

# Chapter 20 — Working with AI Coding Agents

\index{AI agents}\index{multi-agent SDLC}\index{dev-agent}\index{advisor}\index{Definition of Done}

I want to tell you this chapter is different from the one I thought I was going
to write.

The version I had sketched — in my head, mid-sprint-eleven — was a practitioner's
guide to driving AI agents on pipeline work: schema-first prompts, treating output
as a junior's PR, the failure modes and their guardrails. Useful, if I say so.
The problem is that by the time this book was being written, something had
shifted: a substantial portion of Culvert itself — the Python parity work, the
contract testing suite, several sprint waves of adapter code — had been built
using precisely this workflow. The worked example *was* the work. Turning it into
advice-in-theory would be dishonest.

So this is not the chapter I thought I was going to write. It is a practitioner's
account of a multi-agent SDLC that was running live while the rest of this book
was drafted, with the real failure modes we caught, the operating contract we
settled on, and the lessons that are now baked into `CLAUDE.md` in this very
repo so the next session does not have to rediscover them.

The slightly embarrassing thing is that Culvert turns out to be well-shaped for
this workflow, almost entirely by accident. We did not design the contract
boundary for agent legibility. We designed it for human auditors and for
portability. It just happens that an LLM and a tired on-call engineer want
roughly the same things: a single authoritative source for each decision, named
patterns, a narrow scope, and a failing build when something is wrong.

## The four roles

The workflow we settled on by Sprint 12 has four distinct roles. They are not
interchangeable. Understanding why each one exists — and what breaks when you
collapse them — is where most of the practical knowledge lives.

**The engineer — Joseph** — sets direction, owns the brand and the book,
picks the next sprint, approves epics, and is the only one who merges
`sprint-N → main` and triggers a release. That last point matters more than it
sounds: the publish to Maven Central and PyPI is **irreversible**. Version numbers
cannot be reclaimed. So the engineer is the gate, and the gate is manual by
design (`CLAUDE.md`:13).

**The architect — Opus** — grooms the backlog into GitHub issues before any code
is written, dispatches dev-agents, mediates the end-of-sprint standup, and
authors the integration commit at sprint close. The architect does not self-merge
into main; that is the engineer's trigger. What the architect *does* do, always,
is verify every agent's work independently before it is merged. The report is
not the verification (`CLAUDE.md`:29).

**Dev-agents — Sonnet** — take one ticket each, have a two-hour wall-clock budget,
post a DoD-checkbox comment per checkbox passed, and open a PR into `sprint-N`
(`CLAUDE.md`:15). They never self-merge. The one-ticket-per-agent constraint is
not an efficiency choice — it is a reviewability choice. A diff that touches one
ticket is reviewable. A diff that touches four is not.

**The advisor — Opus** — reviews every dev-agent return and is called before the
architect declares any sprint task done (`CLAUDE.md`:16). This is the design
choice I underestimated most. The advisor is a second Opus pass over work that a
first Opus pass dispatched. The friction is the point. We run at most four
dev-agents concurrently and one advisor reviewing their returns. The advisor is
the real throughput bottleneck **by design** — never let parallel returns degrade
reviews into rubber-stamps. The first time I loosened this and let three returns
stack up unreviewed, we shipped a test double that was still calling the old
method signature. The review that catches that takes ten minutes. The debug that
misses it can take a morning.

## The dispatch mechanics

By Sprint 12 we had learned enough hard lessons to write them down
(`CLAUDE.md`:25–32). They are reproduced here because the lessons are load-bearing.

The first and most counter-intuitive: **pre-create each agent's worktree yourself,
off the sprint branch, before dispatching**. The `Agent` tool's
`isolation:"worktree"` flag creates a worktree branching from the repo's *default*
branch — `main` — not from the sprint branch you are working on. An agent in
wave two, dispatched naïvely, would silently build against the state of main and
miss everything wave one had landed. The fix is simple: run
`git worktree add -b feature/<ticket> .claude/worktrees/<id> sprint-N` yourself,
point the agent at that path. We have never lost work from this once the rule was
written down (`CLAUDE.md`:27).

The second: **tell each agent to keep its final report short**. Long return reports
have repeatedly triggered socket-timeout errors that drop the agent. The work
usually commits before the drop. If a return errors, the right move is to check
the worktree for a clean commit and verify it independently, not to re-dispatch
blind (`CLAUDE.md`:28). Two re-dispatches in succession that both time out, with
the first agent's commit already in the worktree, produce a mess that takes longer
to untangle than the original work.

The third: **verify every claim independently**. "Agent says green" is not green.
The report can be lost to a socket drop while the commit survives; the report can
also be optimistic while the commit is broken. Run the build yourself
(`CLAUDE.md`:29).

The fourth, which bit us across two file-touchpoint merges in Sprint 10–11:
**merge order matters when two branches touch the same file**. A pom.xml union
that looks clean from `git merge-tree` against today's tip can still conflict on
merge if the second branch took a different parent. Resolve as UNION, do not
take-one. The T10.6/T10.7 lesson (`CLAUDE.md`:31).

## The Definition of Done

The dispatch checklist tells you *how to run* a sprint wave. The Definition of
Done tells you *what an agent's work must be before it can be merged*. We wrote
this down after Sprint 17, when the architect had to catch several issues the
DoD would have stopped at the agent itself (`CLAUDE.md`:34–45).

**First: run the full package suite, not just the new tests.** If you change a
shared type — a `Protocol`, a record, an interface — you break its implementers
and test doubles elsewhere. An agent that only runs the tests it wrote will
produce a green report on a broken codebase. Before claiming done: `grep` for
every implementer and fake of the symbol changed, update them in the same
changeset, run the whole package's tests (`CLAUDE.md`:36).

**Second: a reproducible environment is part of "done"**. Not a claim that tests
passed — a verbatim command sequence and a count. For Python:

```
python3 -m venv /tmp/vw_<id> && /tmp/vw_<id>/bin/pip install -q -e <pkg> \
  [-e <each-local-dep>] pytest && /tmp/vw_<id>/bin/python -m pytest <pkg>/tests -q
```

For Java: `mvn -o -pl <module> -am test`. The architect re-runs these verbatim.
If they do not reproduce, the work is not done. "No env / did not run" is a
stop-and-report, not a completion (`CLAUDE.md`:37–40).

**Third: cite every cross-language claim** as `file:line`. "This Python
implementation mirrors the Java contract" is an assertion. "mirrors
`StageMetrics.java:27`" is a checkable claim (`CLAUDE.md`:41).

**Fourth: flag, do not fake.** If a guarantee genuinely does not fit, or an
environment cannot be built offline, say so precisely and stop. A flagged gap is
correct. A silent or invented green is not (`CLAUDE.md`:42).

**Fifth: no redundancy, keep the repo current**. When work changes a fact stated
elsewhere — a contract count, a "no X yet" note, a status line — `grep` the repo
for that fact and update every reference in the same change. A stale doc reads as
truth (`CLAUDE.md`:43).

The last sentence of the DoD section is the one I would frame:

> *The architect still verifies independently — but a DoD-conformant report should
> make that a confirmation, not a rescue.* (`CLAUDE.md`:45)

That is the design intent of the whole system. The dev-agent does the work
correctly by construction. The architect confirms. No rescuing.

## Four failure modes we actually saw

The failures we caught are worth naming specifically, because the DoD items above
are not abstract: they each correspond to a concrete thing that went wrong.

### Voiceless drafts

The first wave of book chapters came back technically correct and completely flat.
Correct paragraph structure, accurate claims, British spelling — and none of
Joseph's voice. The chapters read like documentation, not memoir. They were
rejected and the non-negotiable standard was written into
`book/CULVERT_BOOK_OUTLINE.md`:25–26:

> *Adapt the nearest v1 passage; do not invent a flatter tone. The first agent
> attempt produced technically-correct but voiceless chapters — that bar is a
> failure, not a draft.*

The fix was in the brief: point the agent at specific line ranges of the v1 prose,
require that voice to carry forward, and ask for war stories rather than
summaries. The v1 passage is not just context — it is a voice anchor, and without
it the agent defaults to its training distribution, which writes documentation.
Technical accuracy without voice is a different kind of wrong.

### Non-reproducible test claims

In Sprint 17, Wave A, a dev-agent returned a report claiming forty-five tests
passed. The environment it had run the tests in was not preserved. The architect
could not reproduce the count. On inspection, the `_FakeBlobStore` test double
still had the old `open()` signature — the agent had changed the underlying
`Protocol` but had not grepped for fakes, had not updated the double, and had not
actually run the full package suite. The forty-five came from an invocation
against a partial environment that only exercised the new tests (`CLAUDE.md`:35).

This is the canonical failure mode. The agent's report can be confident and wrong.
The test claim is not the test result. The DoD's reproducible-env requirement
(item 2, `CLAUDE.md`:37–40) exists solely because of this incident.

### Socket-dropped agents recovered

Long return reports triggered socket timeouts on three separate occasions. In two
of them, the agent's work had committed cleanly to the worktree before the drop.
The right recovery in both cases was to check the worktree, find the commit,
verify it independently, and merge. Re-dispatching blind would have duplicated
work or introduced a conflict (`CLAUDE.md`:28–29).

The lesson is not that agents are unreliable — it is that the *commit* is the
durable artefact, not the *report*. Write the work first; report second. An agent
that front-loads its prose summary and saves the commit for last inverts the
durability order at exactly the wrong moment.

### From-memory drift

On two occasions early in the sprint cadence, an agent cited "we agreed X" or
made a claim about a file's content from what was evidently training-time memory
rather than reading the actual file. In one case the file had changed in the
previous sprint wave; the agent's claim was correct for a version that no longer
existed.

The rule — "never act on a guessed file path or an unverifiable 'we agreed X'
claim; read the actual file / git history / issue first" — is in `CLAUDE.md`:23
because the alternative is subtle wrong that is hard to catch in review. It looks
right. The failure mode of an agent confidently citing a fact it cannot see is
different from the failure mode of an agent admitting it does not know. The
former is much more dangerous.

## What the framework gives you

The Culvert contract boundary turns out to be well-shaped for agent work, for the
same reason it is well-shaped for testing: every adapter implements a named
interface that is the single authoritative source for what the contract means. An
agent looking at a `GcsBlobStore` implementation knows exactly which interface it
must satisfy. There is no ambiguity about what "matches the contract" means; it
means "compiles and passes the contract test suite."

This is not a property of agents specifically. It is a property of explicit
contracts. But explicit contracts are unusually valuable in an agentic context
because agents cannot hold implicit conventions the way a human team can. A human
engineer on their second week knows that every BlobStore implementation puts the
`open()` return type in a specific place because they have seen it five times in
review. An agent knows it because the `BlobStore` interface at
`data-pipeline-core-java/.../contracts/BlobStore.java` says so. The language-neutral
contract spec at `docs/CONTRACT.md` means there is exactly one place to point an
agent at, in either language, and that place is authoritative.

The DoD's `file:line` citation requirement is the cross-language version of this.
"Mirrors the Java contract" is unverifiable assertion. "Mirrors
`BlobStore.java:14`" is verifiable claim. The contract boundary makes those claims
meaningful because the boundary is explicit.

## What agents can and cannot do

Honest list, grounded in what we have actually observed.

**They can:** produce the mechanical parts of a polyglot translation — finding
implementers, updating test doubles, wiring the expected interfaces, adapting
boilerplate — faster than a human and at a quality that, when the DoD is followed,
makes verification a confirmation rather than a rescue. The Python parity work
(Sprint 17, tracked in `docs/framework-evolution/13-python-parity-release.md`)
moved faster than it would have without agents, and the correctness bar held.

**They cannot:** make the strategic calls — which adapters to build next, whether
to defer Python cloud-neutral skeletons to a later block
(`docs/framework-evolution/13-python-parity-release.md`:strategy), when a module
is truly at release quality versus plausibly green. Those calls need the engineer's
context. An agent will produce a defensible answer to any of them. It will not
produce the right one.

**They cannot:** be left to accumulate redundancy. Stale docs read as truth. A
"no X yet" note that is still in place after X has shipped is a lie that future
agents will propagate. The no-redundancy DoD item is not about cleanliness —
it is about epistemic hygiene in a codebase that agents will read.

**They cannot:** argue back. An agent will produce whatever you ask for, even when
the ask is incoherent. The discipline of arguing back — "this design is wrong
because..." — has to come from the architect. That is not a limitation that will
go away; it is a structural property of the role the agent is playing. The
architect's job is partly to ask questions the agent cannot ask of itself.

**They cannot:** replace the Joseph pass. The authorship model in
`book/CULVERT_BOOK_OUTLINE.md`:11–13 is: agents draft, architect integrates, Joseph
owns the final voice. That ordering exists because the agent can be technically
correct and completely wrong about register, emphasis, which war story to lead
with, and what the reader needs to hear. The first chapter that came back voiceless
is the evidence.

## The operating contract as a first-class document

The lessons above are not in this chapter only. They are in `CLAUDE.md` at the
root of the Culvert repo, written in the operating-contract style of a document
that agents read at the start of every session. That is a deliberate choice.

A decision that lives only in a book chapter is advice. A decision that lives in
the repo, in a document the architect reads before dispatching, is a constraint.
The dispatch checklist at `CLAUDE.md`:25–32 and the DoD at `CLAUDE.md`:34–45
are constraints, not suggestions. The architect enforces them; there is no harness
setting that enforces them automatically (`CLAUDE.md`:21). The discipline is
carried by the human in the architect role, not by the tooling.

This is the honest version of "it worked." It worked because someone read the
rules before each sprint. The rules are good rules. But they are rules, and rules
require a reader.

\begin{takeaways}
\textbf{Key takeaways}
\begin{itemize}
  \item The multi-agent SDLC that built Culvert has four roles: engineer
    (direction, release gate), architect (dispatch, integration, independent
    verify), dev-agent (one ticket, ≤2h, PR into \texttt{sprint-N}), advisor
    (reviews every return, never a rubber-stamp). Collapsing roles collapses
    the review quality that makes the model safe.
  \item The two most counter-intuitive mechanics: pre-create each agent's
    worktree off \texttt{sprint-N} yourself (the \texttt{isolation:"worktree"} flag
    branches from main, not from your sprint branch); and keep final reports
    short (long reports trigger socket timeouts that drop the agent after
    the commit is already written — the commit is the durable artefact,
    not the report).
  \item The Definition of Done is not a quality bar, it is a correctness-by-construction
    design. Full-suite green (not just new tests), reproducible env with exact
    commands and counts, \texttt{file:line} citations for cross-language claims,
    flag-don't-fake on gaps, no stale docs left behind. A DoD-conformant
    report makes architect verification a confirmation, not a rescue.
  \item The four failure modes we actually saw: voiceless drafts (technically
    correct, wrong register — the fix is a voice anchor in the brief, not a
    different agent); non-reproducible test claims (the \texttt{\_FakeBlobStore}
    incident — a confident count from an env no one left behind); socket-dropped
    agents recovered via worktree commit (not re-dispatch); from-memory drift
    on "we agreed X" claims against files that had since changed.
  \item Culvert's explicit contract boundary — one interface per contract,
    language-neutral spec at \texttt{docs/CONTRACT.md} — gives agents exactly
    what they need: an authoritative single source with no implicit conventions.
    It was designed for human auditors; it serves agents for the same reason.
    Technical accuracy without that anchor is a different kind of wrong.
\end{itemize}
\end{takeaways}

\newpage

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

The concrete path for Java: implement `Source<T>` and `Sink<T>`, describe your pipeline as a `Pipeline` (which supplies the stage list and a `validate()` call to check the graph — `data-pipeline-core-java/.../contracts/Pipeline.java:29`), and build a `DefaultRuntimeContext` with `DefaultRuntimeContext.builder(runId, "prod").build()`. The BigQuery warehouse, the GCS blob store, the Pub/Sub audit publisher — all of them arrive via `AutoConfig.discover()` at bootstrap, which uses `ServiceLoader` to find and register every adapter on the classpath into the context (`README.md:69`). Your pipeline code never imports `GcsBlobStore` or `BigQueryWarehouse` directly. It calls `context.get(BlobStore.class)`, and the ServiceLoader machinery hands back the right one.

The concrete path for Python is structurally identical: use the Protocols from `data-pipeline-core/contracts/`, construct a `DefaultRuntimeContext`, and call `AutoConfig.discover()` at bootstrap to wire the adapters in `data-pipeline-gcp-bigquery`, `-gcs`, `-pubsub` under the `data_pipeline_core.adapters` entry-point group. Your business logic writes against the protocol surface; `AutoConfig` handles the rest.

The contract-tests module — `data-pipeline-contract-tests*` — is where conformance is enforced. Every adapter must pass those tests; every new adapter you write should bind to them. Chapter 16 covers this in full. The point here is that the test suite tells you whether your adapter is conformant, not whether your adapter works. Those are different questions; the contract tests answer the first one systematically, and your integration tests answer the second.

## A day: run the full integration tests

Once you have the Docker daemon available, the integration tests exercise the full round-trip via Testcontainers — local GCS/BigQuery emulators, no real GCP project required at this tier:

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

**Wave C — adapter parity (done).** The Python `SecretManagerProvider` and the Python `gcp-observability` package (CloudTrace hook, DataCatalog lineage, CloudMonitoring metrics) have landed, along with per-service cost trackers for the Python BigQuery, GCS, and Pub/Sub modules. (`README.md:81`)

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

# Appendix A — Library Reference

This appendix is a compact reference to the public surface of every Culvert library. It is intentionally telegraphic — a lookup table, not a tutorial. Consult the module README or the contract Javadoc / docstring for the full API. All libraries are at version **0.1.0**, built and held; nothing has been published to Maven Central or PyPI yet. The coordinated release under the `culvert` namespace is future work. Java `groupId` is `com.enrichmeai.culvert`; Python distributions are currently named `data-pipeline-*`.

---

## A.1 Contract quick-reference

The sixteen cloud-neutral contracts live in `data-pipeline-core-java` (Java interfaces) and `data-pipeline-core` (Python `@runtime_checkable Protocol`s). Every adapter in the framework implements one or more of these; every pipeline author codes against them.

| Contract | Language mirror | One-line purpose |
|---|---|---|
| `Source<T>` | `Source[T]` | Yields records into the pipeline |
| `Sink<U>` | `Sink[U]` | Consumes records out of the pipeline |
| `Transform<V,W>` | `Transform[V,W]` | Maps records V → W |
| `Pipeline` | `Pipeline` | Composition of stages, scheduler-agnostic |
| `PipelineStage` | `PipelineStage` | Named, dependency-aware unit of work |
| `RuntimeContext` | `RuntimeContext` | DI container: config, secrets, adapter registry |
| `BlobStore` | `BlobStore` | Object-storage abstraction (gs://, s3://, abfs://) |
| `Warehouse` | `Warehouse` | Tabular query/load abstraction |
| `JobControlRepository` | `JobControlRepository` | Pipeline-job state-machine |
| `SecretProvider` | `SecretProvider` | Single seam for secret lookup |
| `AuditEventPublisher` | `AuditEventPublisher` | At-least-once audit-record delivery |
| `ObservabilityHook` | `ObservabilityHook` | Unified metrics/logs/tracing seam |
| `LineageEmitter` | `LineageEmitter` | Publishes lineage events at stage boundaries |
| `FinOpsSink` | `FinOpsSink` | Receives cost metrics with attribution tags |
| `GovernancePolicy` | `GovernancePolicy` | Resolves masking, retention, classification |
| `StageMetricsHook` | `StageMetricsHook` | Emits per-stage pipeline metrics (narrow) |

`StageMetrics` is the accompanying value type (not a contract) — an immutable snapshot carrying `rowsProcessed`, `stageLatencyMs`, and `errorCount` labelled by `pipelineId`, `runId`, and `stageName`.

Sources:
- Java interfaces — `data-pipeline-libraries-java/data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/` (17 files)
- Python Protocols — `data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/contracts/__init__.py:1–35`

---

## A.2 Java reactor modules

The Java side of Culvert is a Maven multi-module build rooted at `data-pipeline-libraries-java/pom.xml`. Thirteen modules in total (`pom.xml:<modules>` block, lines 6–50).

### Core (contracts)

**`data-pipeline-core`** (`data-pipeline-core-java/pom.xml:<description>`)
The cloud-neutral kernel: the sixteen contract interfaces above, plus the supporting records, enums, and value types those interfaces reference (`AuditRecord`, `LineageEvent`, `EntitySchema`, `CostMetrics`, `FinOpsTag`, `StageMetrics`, …). No GCP, AWS, or Azure SDK imports. This is the only module pipeline authors must depend on at compile time.

### GCP adapters

**`data-pipeline-gcp-secrets`** (`data-pipeline-gcp-secrets-java/pom.xml:<description>`)
`SecretManagerProvider` — a `SecretProvider` wrapping `com.google.cloud.secretmanager.v1.SecretManagerServiceClient`. Registered via `java.util.ServiceLoader` so consumers wire it without compile-time coupling to the GCP SDK.

**`data-pipeline-gcp-bigquery`** (`data-pipeline-gcp-bigquery-java/pom.xml:<description>`)
`BigQueryWarehouse` — a `Warehouse` wrapping `com.google.cloud.bigquery.BigQuery`. Also houses the `JobControlRepository` (BigQuery-backed) and `FinOpsSink` (BigQuery-backed) adapters for the same cloud.

**`data-pipeline-gcp-gcs`** (`data-pipeline-gcp-gcs-java/pom.xml:<description>`)
`GcsBlobStore` — a `BlobStore` wrapping `com.google.cloud.storage.Storage`. URIs are `gs://`-prefixed; the adapter parses them; the contract does not.

**`data-pipeline-gcp-pubsub`** (`data-pipeline-gcp-pubsub-java/pom.xml:<description>`)
`PubSubSource` (synchronous pull via `SubscriberStub`) and `PubSubSink` (publish via `Publisher`) — `Source` and `Sink` implementations for Google Cloud Pub/Sub.

**`data-pipeline-gcp-observability`** (`data-pipeline-gcp-observability-java/pom.xml:<description>`)
Two adapters in one module: `CloudTraceObservabilityHook` (spans exported to Cloud Trace via the OpenTelemetry GCP exporter, implements `ObservabilityHook`) and `DataCatalogLineageEmitter` (lineage events written as Data Catalog tags, implements `LineageEmitter`).

**`data-pipeline-gcp-dataflow`** (`data-pipeline-gcp-dataflow-java/pom.xml:<description>`)
`DataflowPipeline` — a `Pipeline` implementation that holds the stage topology and provides `buildBeam()` (translates the stage graph to an Apache Beam `Pipeline`) and `runOnDataflow()` (submits via `DataflowPipelineRunner`).

### Cloud-neutral skeletons (AWS / Azure)

**`data-pipeline-aws-s3`** (`data-pipeline-aws-s3-java/pom.xml:<description>`)
`S3BlobStore` — a `BlobStore` skeleton over `software.amazon.awssdk:s3`. One method implemented (`exists`); the rest throw `UnsupportedOperationException`. Sprint-8 deliverable: proves the cloud-neutral design accommodates AWS without any change to the contracts.

**`data-pipeline-azure-blob`** (`data-pipeline-azure-blob-java/pom.xml:<description>`)
`AzureBlobStore` — a `BlobStore` skeleton over `com.azure:azure-storage-blob`. Same shape as the S3 skeleton. Sprint-8 deliverable for Azure.

### Orchestration

**`data-pipeline-orchestration`** (`data-pipeline-orchestration-java/pom.xml:<description>`)
Cloud-neutral DAG model: `DagSpec` / `TaskSpec` value types and a `Pipeline → DagSpec` translator. No Beam, no Airflow, no GCP imports — depends only on `data-pipeline-core` and `java.util`. Renderer modules (Airflow / Composer) build on top.

### Test support

**`data-pipeline-tester`** (`data-pipeline-tester-java/pom.xml:<description>`)
Mockito-helper fixture builders for the five most-mocked contracts (`SecretProvider`, `Warehouse`, `BlobStore`, `JobControlRepository`, `FinOpsSink`). Eliminates repetitive `when(…).thenReturn(…)` boilerplate in consumer unit tests. Mockito and AssertJ are `compile`-scope deps here — this is a test library.

**`data-pipeline-it-support`** (`data-pipeline-it-support-java/pom.xml:<description>`)
Reusable Testcontainers fixtures for integration tests: BigQuery emulator (`goccy/bigquery-emulator`), GCS fake (`fsouza/fake-gcs-server`), and helpers that build GCP SDK clients pointed at those emulators. Pub/Sub uses Testcontainers' built-in `PubSubEmulatorContainer` directly.

**`data-pipeline-contract-tests`** (`data-pipeline-contract-tests-java/pom.xml:<description>`)
Abstract JUnit contract test classes. Cloud adapter modules extend the relevant class and supply the adapter under test; the abstract tests verify the adapter honours the protocol's documented behaviour. Every GCP adapter passes these before sprint sign-off.

---

## A.3 Python packages

The Python side of Culvert is a set of independently-installable packages under `data-pipeline-libraries/`. All are at `0.1.0`.

### Core (contracts)

**`data-pipeline-core`** (`data-pipeline-libraries/data-pipeline-core/pyproject.toml`)
Cloud-neutral kernel: `@runtime_checkable Protocol`s (the sixteen contracts), supporting dataclasses, and value types. Zero GCP/AWS/Azure SDK dependencies. The Python mirror of `data-pipeline-core-java`.

### GCP adapters

**`data-pipeline-gcp-secrets`** (`data-pipeline-libraries/data-pipeline-gcp-secrets/pyproject.toml`)
`SecretManagerProvider` — `SecretProvider` Protocol backed by `google-cloud-secret-manager`.

**`data-pipeline-gcp-gcs`** (`data-pipeline-libraries/data-pipeline-gcp-gcs/pyproject.toml`)
`GcsBlobStore` — `BlobStore` Protocol backed by `google-cloud-storage`. Counterpart to the Java module of the same name.

**`data-pipeline-gcp-bigquery`** (`data-pipeline-libraries/data-pipeline-gcp-bigquery/pyproject.toml`)
`BigQueryWarehouse` — `Warehouse` Protocol backed by `google-cloud-bigquery`. Also houses BigQuery-backed `JobControlRepository` and `FinOpsSink` adapters.

**`data-pipeline-gcp-pubsub`** (`data-pipeline-libraries/data-pipeline-gcp-pubsub/pyproject.toml`)
`PubSubSource` / `PubSubSink` — `Source` / `Sink` Protocols backed by `google-cloud-pubsub`.

**`data-pipeline-gcp-observability`** (`data-pipeline-libraries/data-pipeline-gcp-observability/pyproject.toml`)
Four adapters: `CloudTraceObservabilityHook` (implements `ObservabilityHook`), `CloudMonitoringStageMetricsHook` (implements `StageMetricsHook`), `DataCatalogLineageEmitter` (implements `LineageEmitter`), and `CulvertMdcPopulator` (log-correlation helper).

### Orchestration

**`data-pipeline-orchestration`** (`data-pipeline-libraries/data-pipeline-orchestration/pyproject.toml`)
Airflow DAG factory, operators, sensors, and callbacks. Cloud-coupled to Composer/Airflow; Airflow is Python-only and is not being ported to Java. Renamed successor of `gcp-pipeline-orchestration`.

### Transform

**`data-pipeline-transform`** (`data-pipeline-libraries/data-pipeline-transform/pyproject.toml`)
dbt macro library: audit columns, PII masking, data-quality checks. dbt-SQL only — no Beam, no Airflow imports. Renamed successor of `gcp-pipeline-transform`.

### Tester

**`data-pipeline-tester`** (`data-pipeline-libraries/data-pipeline-tester/pyproject.toml`)
Base test classes, builders, assertions, BDD steps, mocks, and fixtures for Source/Sink/Transform pipelines and their cloud adapters. pytest and `data-pipeline-core` are compile-time deps. Renamed successor of `gcp-pipeline-tester`.

### Contract tests

**`data-pipeline-contract-tests`** (`data-pipeline-libraries/data-pipeline-contract-tests/pyproject.toml`)
Abstract pytest contract tests that every Culvert adapter implementation must pass. Python counterpart to `data-pipeline-contract-tests-java`.

### Umbrella

**`data-pipeline-framework`** (`data-pipeline-libraries/data-pipeline-framework/pyproject.toml`)
Metapackage: installs the full reference stack (core + tester + transform + orchestration). Bundles deployment templates, Terraform modules, and CI workflow templates as embedded assets. No public API of its own.

---

## A.4 Summary by group

| Group | Java modules | Python packages |
|---|---|---|
| Core (contracts) | `data-pipeline-core` | `data-pipeline-core` |
| GCP adapters | `data-pipeline-gcp-secrets`, `-gcp-bigquery`, `-gcp-gcs`, `-gcp-pubsub`, `-gcp-observability`, `-gcp-dataflow` | `data-pipeline-gcp-secrets`, `-gcp-gcs`, `-gcp-bigquery`, `-gcp-pubsub`, `-gcp-observability` |
| Cloud-neutral skeletons | `data-pipeline-aws-s3`, `-azure-blob` | — |
| Orchestration | `data-pipeline-orchestration` | `data-pipeline-orchestration` |
| Transform (dbt) | — | `data-pipeline-transform` |
| Tester | `data-pipeline-tester` | `data-pipeline-tester` |
| IT support | `data-pipeline-it-support` | — |
| Contract tests | `data-pipeline-contract-tests` | `data-pipeline-contract-tests` |
| Umbrella | — | `data-pipeline-framework` |

**Totals:** 13 Java modules, 11 Python packages.

\newpage

# Appendix B — Directory Map

The layout below reflects the repository as it stands at v0.1.0 — built and held, not yet published to Maven Central or PyPI. The structure has two active library trees (Java and Python) and one legacy tree that is being retired.

Source of truth: `README.md:29–47`.

```
culvert/                              # repo root (codename; customer brand: Valuedocs Legal)
├── README.md
├── VERSION
├── pyproject.toml
├── reconstruct.py
├── qodana.yaml
│
├── data-pipeline-libraries-java/     # Java reactor — Maven, groupId com.enrichmeai.culvert
│   ├── pom.xml                       # parent POM (13 modules)
│   ├── data-pipeline-core-java       # contracts + records + AutoConfig (ServiceLoader)
│   ├── data-pipeline-gcp-bigquery-java
│   ├── data-pipeline-gcp-gcs-java
│   ├── data-pipeline-gcp-pubsub-java
│   ├── data-pipeline-gcp-secrets-java
│   ├── data-pipeline-gcp-observability-java
│   ├── data-pipeline-gcp-dataflow-java
│   ├── data-pipeline-aws-s3-java     # cloud-neutrality skeleton (not yet complete)
│   ├── data-pipeline-azure-blob-java # cloud-neutrality skeleton (not yet complete)
│   ├── data-pipeline-orchestration-java  # DagSpec/TaskSpec + Airflow/Composer renderers
│   ├── data-pipeline-contract-tests-java
│   ├── data-pipeline-tester-java
│   └── data-pipeline-it-support-java
│
├── data-pipeline-libraries/          # Python library set
│   ├── data-pipeline-core            # Protocols + records + AutoConfig (entry-points)
│   ├── data-pipeline-gcp-bigquery
│   ├── data-pipeline-gcp-gcs
│   ├── data-pipeline-gcp-pubsub
│   ├── data-pipeline-gcp-secrets
│   ├── data-pipeline-gcp-observability
│   ├── data-pipeline-orchestration
│   ├── data-pipeline-transform       # dbt is SQL + macros; no Java twin by design
│   ├── data-pipeline-tester
│   ├── data-pipeline-contract-tests
│   └── data-pipeline-framework       # umbrella: installs all sibling packages
│
├── deployments/                      # reference pipelines built on the framework
│   ├── original-data-to-bigqueryload/    # ingestion (Beam)
│   ├── bigquery-to-mapped-product/       # FDP transform (dbt)
│   ├── fdp-to-consumable-product/        # CDP transform (dbt)
│   ├── data-pipeline-orchestrator/       # DAGs (Airflow)
│   ├── mainframe-segment-transform/      # FDP → mainframe (Beam, Python)
│   ├── mainframe-segment-transform-java/ # FDP → mainframe (Beam, Java)
│   ├── spanner-to-bigquery-load/         # federated (dbt)
│   ├── postgres-cdc-streaming/           # streaming reference (Beam)
│   ├── fdp-trigger/                      # downstream notification
│   └── reference-e2e-gcp/                # end-to-end GCP smoke suite
│
├── docs/                             # 30+ design and operations guides
│   └── framework-evolution/          # canonical "why / what / when" for the redesign
│       ├── 01-audit.md               # cloud-neutral audit that started it all
│       ├── 02-redesign.md
│       ├── 03-dev-process.md
│       ├── 04-sprint-plan.md
│       ├── 06-sprint-plan-9-16.md
│       ├── 10-architecture.md
│       └── 13-python-parity-release.md   # polyglot release gate spec
│
├── book/                             # this manuscript
│   ├── CULVERT_BOOK_OUTLINE.md
│   ├── gcp-pipeline-book.md          # v1 raw material (memoir-grade prose)
│   ├── gcp-pipeline-book.pdf / .epub / .tex
│   └── chapters/                     # drafted chapters (one file per chapter)
│
├── infrastructure/
│   └── terraform/                    # GCP infrastructure-as-code
│       ├── main.tf
│       ├── security.tf
│       ├── dataflow.tf
│       └── systems/generic/
│           ├── ingestion/
│           ├── transformation/
│           └── orchestration/
│
├── scripts/                          # bootstrap and helper scripts
├── templates/                        # DAG, dbt, Dockerfile starters
├── test_data/                        # CSV fixtures (HDR/TRL envelope pattern)
└── gcp-pipeline-libraries/           # earlier GCP-only iteration — retired, being removed
```

## A note on the legacy tree

The `gcp-pipeline-libraries/` subtree is the predecessor framework — `groupId`-style package names beginning `gcp_pipeline_*`. It is retired in place: the code still exists as origin evidence but is not under active development. The v1 book manuscript's directory map (lines 5307–5313 of `gcp-pipeline-book.md`) shows this tree as the primary structure; that was accurate for the predecessor and is superseded here. The current framework lives exclusively in `data-pipeline-libraries-java/` (Java) and `data-pipeline-libraries/` (Python).

## What the two-tree split means in practice

The Java reactor is a Maven multi-module build whose parent POM lives at `data-pipeline-libraries-java/pom.xml`. Each module is a separate Maven artefact under `groupId com.enrichmeai.culvert`. The thirteen modules map cleanly onto the contract families: core (contracts + records + ServiceLoader discovery), one module per GCP service, two cloud-skeleton modules (AWS S3, Azure Blob), orchestration, and three test-support modules.

The Python library set mirrors the same contract families as separate distributions (currently named `data-pipeline-*`, with `culvert` as the planned coordinated-release name on PyPI). The `data-pipeline-transform` module has no Java twin: dbt is SQL and macros and is therefore language-neutral by nature — one Python package serves both runtimes.

\newpage

# Appendix C — A Cost Model

I want to be honest with you about money. Cloud cost is the thing that surprises engineering teams the most — not because the per-unit pricing is hidden, but because the multiplication happens faster than you expect once you move from a proof of concept to a real daily pipeline. So this appendix does two things: it shows you where the constants in Culvert's FinOps trackers come from, and it walks a worked example from raw bytes all the way to a dollar figure.

## The tracker constants (exact source)

Culvert's cost model is not a hand-waved ballpark. The numbers are baked into three Java source files, tested, and wired into the `FinOpsSink` chain. Here they are:

**BigQuery** (`data-pipeline-libraries-java/data-pipeline-gcp-bigquery-java/src/main/java/com/enrichmeai/culvert/gcp/bigquery/BigQueryCostTracker.java`):

- `BYTES_PER_TIB = 1_099_511_627_776L` (line 81) — 2^40, the binary tebibyte. The Javadoc is explicit: use the binary definition, not 10^12, or you will undercount by roughly 10 %.
- `QUERY_COST_USD_PER_TIB = 5.00` (line 90) — GCP on-demand query rate as of 2025.
- `LOAD_COST_USD_PER_TIB = 0.01` (line 103) — an accounting placeholder, not an actual BigQuery charge. Batch loads are free to ingest; this constant attributes an egress-equivalent rate for teams that want every data-movement event in their cost ledger. Set it to 0.0 if that is not your convention.

**Pub/Sub** (`data-pipeline-libraries-java/data-pipeline-gcp-pubsub-java/src/main/java/com/enrichmeai/culvert/gcp/pubsub/PubSubCostTracker.java`):

- `BYTES_PER_TIB = 1_099_511_627_776L` (line 65) — same binary definition, mirrored for consistency.
- `THROUGHPUT_COST_USD_PER_TIB = 40.00` (line 81) — GCP on-demand message throughput rate. The first 10 GiB/month is free; the tracker records gross cost with no free-tier deduction. The Javadoc on line 73–80 includes a useful correction: an earlier ticket draft said "$0.04/MiB", which is approximately 1,000× the actual rate — the constant uses the correct per-TiB billing unit.

**GCS** (`data-pipeline-libraries-java/data-pipeline-gcp-gcs-java/src/main/java/com/enrichmeai/culvert/gcp/gcs/GcsCostTracker.java`):

- `BYTES_PER_GIB = 1_073_741_824L` (line 77) — 2^30. GCS pricing is quoted in GiB-months, not TiB.
- `WRITE_COST_USD_PER_GIB = 0.01` (line 90) — accounting placeholder (GCS bills Class A operations per 10,000, not per byte).
- `STANDARD_STORAGE_USD_PER_GIB = 0.020` (line 99) — US multi-region Standard, 2025.
- `NEARLINE_STORAGE_USD_PER_GIB = 0.010` (line 108).
- `COLDLINE_STORAGE_USD_PER_GIB = 0.004` (line 117).
- `ARCHIVE_STORAGE_USD_PER_GIB = 0.0012` (line 126).

## The cost formulas

```
-- BigQuery query job
estimatedCostUsd = billedBytesScanned / BYTES_PER_TIB * QUERY_COST_USD_PER_TIB

-- Pub/Sub publish or subscribe
estimatedCostUsd = totalBytes / BYTES_PER_TIB * THROUGHPUT_COST_USD_PER_TIB

-- GCS storage (monthly)
estimatedCostUsd = bytesStored / BYTES_PER_GIB * rateForStorageClass
```

These are not simplifications for the book. They are the exact expressions in `BigQueryCostTracker.bytesToUsd()` (line 321–326), `PubSubCostTracker.bytesToUsd()` (line 182–187), and `GcsCostTracker.bytesToUsd()` (line 244–249).

## A worked example — one entity, one month

Imagine a single data entity running through the full pipeline daily: an extract from a source system, landing in GCS, triggering a Beam/Dataflow ingestion job into BigQuery ODP, transformed via dbt into FDP, and queried downstream for reporting. At moderate volume — five million rows, averaging 500 bytes per row — here is what the maths says.

### Step 1 — Raw bytes

```
rows per day        : 5,000,000
bytes per row       : 500
bytes per daily run : 5,000,000 × 500 = 2,500,000,000 bytes ≈ 2.33 GiB
bytes per month     : 2,500,000,000 × 30 = 75,000,000,000 bytes ≈ 69.9 GiB
```

### Step 2 — GCS landing storage

The raw files sit in a Standard bucket (landing zone) for 7 days, then move to Coldline (archive). Call it 20 GiB Standard on average at any one time, plus 50 GiB Coldline for the rolling archive.

```
Standard : 20 GiB × $0.020/GiB  = $0.40
Coldline : 50 GiB × $0.004/GiB  = $0.20
GCS total                        ≈ $0.60
```

Using the tracker formula: `bytesStored / BYTES_PER_GIB * COLDLINE_STORAGE_USD_PER_GIB`
= `53,687,091,200 / 1_073_741_824 × 0.004` = $0.20. The maths is exact.

### Step 3 — Pub/Sub trigger

Each daily run publishes one trigger message (negligible bytes). 30 messages/month × 1 KB each = 30 KB total — well inside the 10 GiB free tier. Gross cost rounds to $0.00 at this volume; the tracker still records the event in the cost ledger.

### Step 4 — BigQuery load (Dataflow → ODP)

Dataflow writes 75 GB/month into BigQuery via load jobs. BigQuery batch loads are free; `LOAD_COST_USD_PER_TIB = 0.01` is an accounting placeholder.

```
load accounting : 75,000,000,000 / 1_099_511_627_776 × 0.01
               ≈ 0.068 TiB × $0.01 = $0.00068 ≈ $0.00
```

Effectively zero. The value of recording it is attribution, not the number itself.

### Step 5 — BigQuery query (dbt + downstream)

Assume dbt runs five queries per day against the ODP, each scanning the full monthly table (69.9 GiB ≈ 0.068 TiB). Plus five ad-hoc analyst queries per day at the same scan rate. Ten queries/day × 30 days × 0.068 TiB = 20.4 TiB scanned in the month.

```
query cost : 20.4 TiB × $5.00/TiB = $102.00
```

Using the tracker formula: `billedBytesScanned / BYTES_PER_TIB × QUERY_COST_USD_PER_TIB`.
This is the line that surprises people. Five million rows, reasonable query patterns, and you are already at $100/month on BigQuery compute for a single entity. At four entities the number is $408 before infrastructure.

The mitigation is partition pruning: if dbt queries filter on the daily partition column, each query scans 2.33 GiB, not 69.9 GiB. The cost drops to `10 queries/day × 30 days × 0.00228 TiB × $5.00` = $3.42/month. That is a 30× difference from one DDL clause.

### Monthly summary — four entities, with and without Composer

| Component | Notes | Monthly USD |
|---|---|---|
| GCS landing + archive (×4 entities) | 80 GiB Standard, 200 GiB Coldline | $2.40 |
| Pub/Sub triggers | Inside free tier | $0.00 |
| Dataflow (ingestion, ×4 entities) | 4 workers × 4 entities × 30 min/day × n1-standard-2 | ~$86 |
| BigQuery load (accounting) | Batch loads are free; placeholder | ~$0.00 |
| BigQuery storage — ODP + FDP + marts | ~1 TiB active, ~1 TiB long-term | ~$25 |
| BigQuery compute (partitioned queries) | ~14 TiB/month scanned at $5.00/TiB | ~$70 |
| Cloud Logging + Monitoring | Structured logs, custom metrics | ~$30 |
| **Subtotal without orchestration** | | **~$213** |
| Cloud Composer 2 (smallest config, 24/7) | Optional; GKE + managed Airflow | ~$300 |
| **Total with Composer** | | **~$513** |

The Composer line is the dominant term and it does not vary with volume. A team running four entities does not need managed Airflow 24 hours a day; the framework's default does not provision it. Viable alternatives are Cloud Functions for the trigger step plus Cloud Run Jobs for scheduled transforms, which lands the orchestration bill in the $20–$40 range.

## What the tracker does with these numbers

The three cost trackers do not make decisions. They observe the bytes-billed numbers returned by GCP APIs after each job, apply the formula above, and emit a `CostMetrics` record to the `FinOpsSink`. The FinOps strategy (`docs/FINOPS_STRATEGY.md`) and `BudgetGovernancePolicy` are where the decision logic lives: alert thresholds, per-entity budget caps, automatic run suspension. The trackers are the sensors; the policy is the actuator.

The dry-run path in `BigQueryCostTracker.estimateDryRun()` (line 193–234) lets you call the formula before you execute — useful for guarding the expensive analyst queries described in Step 5 above. Submit a dry-run, get the estimated bytes, reject the job if it exceeds your threshold. Whether the BigQuery API reliably populates `getTotalBytesBilled()` on a dry-run is flagged in the source Javadoc (lines 48–60) as a runtime verification risk to check in the integration test (`BigQueryCostTrackerIT`).

\newpage

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

# About the Author

**Joseph Aruja** is a Senior Lead Engineer based in Leeds, UK, with twenty-five years of hands-on experience building production systems for banks, government departments, retailers, transport authorities, automotive OEMs, healthcare bodies, and travel platforms.

He is a member of the JSR 255 (JMX) specification group within the Java Community Process, holds an MSc in Information Systems and the BCS Practitioner Certificate in Enterprise & Solution Architecture. He has worked across the full lifecycle of distributed-systems engineering — from architecture and solution design through to mentoring teams and writing production code himself, often on the same project.

His career has alternated deliberately between **regulated industries** and **scale-driven engineering**:

- **National-scale public services.** Technical lead for the NHS Spine Release 7A, contributing to ETP (Electronic Transmission of Prescriptions), DSA (Demographic Spine Application), QMAS, and XTS — services that, between them, underpin a substantial share of UK primary-care infrastructure. Designed the SAML-based single-sign-on framework reused across every Spine module, and built the proof-of-concept that replaced the Common Services Framework's custom messaging stack with Apache Camel.

- **Financial services.** Microservices for HSBC, First Direct, and M&S Bank across loans, current accounts, credit cards, and savings (12 live services under FCA compliance, reactive microservices on Spring Boot + RxJava + Kotlin). Currently Senior Lead Engineer on a financial-services mainframe-to-cloud migration. Earlier work on pricing automation for Allstate Insurance (Kafka-orchestrated rate-to-market platform).

- **Government compliance.** Home Office Asylum Services (microservices architecture for case-working), UK Border Agency Employment Checking Service (application security and integration), DWP Universal Credit Evidence subsystem, GOV.UK Home Office Framework (Audit Logging and Product Catalogue migration from Postgres to Redis).

- **Mainframe-to-modern integration.** This book's lineage starts here. Wm Morrison Supermarkets' Evolve programme (2009–2010): subject-matter expert for integrating Oracle Retail Price Management and Oracle Retail Merchandising with the legacy mainframe via the Oracle Retail Integration Bus, Oracle SOA Suite, BPEL, AIA reference architecture, Oracle AQ, and custom HP OpenView monitoring.

- **High-volume consumer platforms.** Booking.com (migrating the on-prem booking engine to AWS EKS, building a scalable reservation-number-provider microservice, swapping Hystrix for Resilience4j), Caesars Digital / William Hill US (EPOS terminal estate, PCI-DSS-compliant authentication, AWS EKS).

- **Connected vehicles.** Jaguar Land Rover, twice. First on the VCS team (migrating event and historic-data frameworks to Java 17 / Spring Boot 3 on GCP); now on the Subscription Control Platform (re-architecting, building internal tooling, setting engineering standards).

- **Smart-city transport.** Smart Ticketing on Greater Manchester Metrolink for Transport for Greater Manchester (with Worldline) — ITSO smart cards and contactless EMV under PCI-DSS, OAuth2, multi-tenant Liferay portal, Spring Webflow, Spring Data + QueryDSL. Public-facing at getmethere.com.

He works fluently across the JVM (Java 8 through 21, Spring Boot, Spring Cloud, Dropwizard, Kotlin) and the Python data ecosystem (Python 3.7+, Apache Beam, dbt, Airflow). The framework this book describes — Culvert — is the consolidation of patterns he has been writing variations of since 2009, when *data pipeline* was still called *integration* and the platform of choice was Oracle SOA Suite.

He writes about data engineering, GCP, and mainframe modernisation on Medium.

**Contact:** joseph.a.aruja@gmail.com
**LinkedIn:** https://www.linkedin.com/in/josepharuja/

\newpage

\addcontentsline{toc}{chapter}{Index}
\printindex

\newpage

# Appendix E — Interviewing for the Work

A framework is only as durable as the next engineer who joins the team. This appendix is the interview format I run when hiring senior data engineers onto a pipeline platform like the one in this book — internal moves and external hires alike. It is not a question bank to be read out verbatim. It is a structure designed to surface, in one hour, whether the person sitting opposite you can actually do the work the rest of the book describes.

I have settled on **six primary questions over sixty minutes, with a three-person panel and one candidate at a time**\index{interviewing}. The panel I prefer is the engineering lead (you, if you have built or operate the platform), the product owner who lives with the data, and a peer engineer from the team the candidate would join. Each person leads two questions; everyone takes notes; nobody dominates. Two candidates back-to-back in a morning is a comfortable cadence and lets the panel calibrate against itself while the conversations are still fresh.

## Why six questions in sixty minutes

Most engineering interviews fail in one of two directions. They either drown the candidate in trivia (name three Beam runners; what does `idempotency_key` do in `BigQueryIO.write`) or they ask one enormous question and run out of time before the answer goes anywhere interesting. Six questions is the sweet spot: enough breadth to cover ingestion, transformation, operations, security, and process; few enough that each conversation can actually breathe. Plan eight to ten minutes per question, leaving four minutes at the start for context and four at the end for the candidate's own questions.

The format below assumes a candidate who has worked on production data pipelines somewhere — not necessarily this stack, but something close enough that the vocabulary lands. If you are interviewing for a junior role, halve the depth and double the patience; the structure is wrong but the topics still cover the right ground.

## Suggested timing

| Block | Minutes | Lead |
|-------|---------|------|
| Welcome, context, role | 4 | Lead |
| Q1 — Ingestion design | 9 | Lead |
| Q2 — Remediation flow | 8 | Product owner |
| Q3 — Duplication: prevent and recover | 9 | Peer engineer |
| Q4 — dbt auth across environments | 7 | Lead |
| Q5 — Two-part data-quality scenario | 11 | Product owner |
| Q6 — CI/CD for data systems | 8 | Peer engineer |
| Candidate's questions | 4 | All |

If a question runs long because the answer is genuinely good, take time off Q6 — not off the candidate's own questions. That last block is where people decide whether to accept your offer.

## The six questions

The questions below are framed as prompts, what to listen for, where to push, and what counts as a red flag. The "what to listen for" sections describe *signals*, not vocabulary — score what the candidate understands, not which exact words they use. Two candidates can describe the same correct architecture in different terms; both should pass.

### Q1 — Design an ODP-to-FDP pipeline from a fixed-width file

> *Lead asks.* "You are landing a daily fixed-width extract — say, 200 GB, twelve million records, a header and trailer with control counts — into a GCS bucket. The business wants a clean BigQuery table downstream. Walk me through the architecture, from the moment the file lands to the point an analyst can query a curated view."

**Listening for.** A clean separation between the *envelope* (header/trailer record-count reconciliation\index{HDR/TRL}) and the *payload* (per-record parsing and validation). A landing-then-promote pattern, not direct-to-BigQuery writes. A bronze/silver/gold or ODP/FDP/CDP layering with a defensible reason for each layer. Schema-as-config rather than hand-rolled column lists. Reconciliation as a first-class step, not a footnote. A coherent story about where the work runs: Dataflow Flex Template for parsing because it scales, dbt-on-Composer (or equivalent) for the transformation, and a clear answer to "why those two and not one or the other".

**Push on.** What happens to records that fail validation — quarantine, dead-letter table, or hard fail the run? How is the run identified end to end, and how does that ID show up in the BigQuery rows themselves\index{run-id}? Where does the schema live — code, a SQL migration, a config file, a contract document? How would the design change if the file arrives in five parts with `.ok` sentinels instead of one\index{split files}?

**The no-golden-path follow-up.** Once the main answer lands, drop this in: *"What if there's no precedent for this — you are the first team to build a pipeline from this source, the source team has not produced a schema for you, and nobody internally has done one of these before. Where do you actually start?"* This is the senior signal you are testing for. You want to hear: ask the source team for a sample file and run statistics; profile it; propose a candidate schema; circulate it for review; build a small, throwaway pipeline against one day's data; only then commit to a long-term design. The opposite of "I'd look at the existing pipeline and copy it".

**Red flags.** Loading the raw file straight into the final BigQuery table. Treating validation as something to add later. No mention of reconciliation. Assuming the schema is fixed and known. Reaching immediately for Composer without considering whether the orchestration needs to be that heavy.

### Q2 — Walk a remediation cycle

> *Product owner asks.* "Yesterday's run finished. This morning we discovered three thousand rows in the foundation table have the wrong account-type code — a downstream business team noticed before we did. The data has already flowed into a consumable view. What do you do, in what order, with whom, on what timeline?"

**Listening for.** Calm, ordered thinking. Stakeholder communication first — "I tell the consumer-facing team we have a known issue and freeze the downstream view" — before any technical remediation. Then a triage step: how many rows, which entity, when did it start, is the source data wrong or did the transformation lie? Then a reversible fix: rerun the affected partition rather than patch values by hand. Then a verification step before unfreezing. Finally a post-incident note that ends up in a runbook, not a Slack thread.

**Push on.** Who owns the call about whether to roll back? What is the SLA promised to the downstream consumers, and does this incident breach it? How would the team know if the bug had been in production for six months instead of one day — and is that a different incident class? What guardrail would prevent the next instance?

**Red flags.** Reaching for `UPDATE` statements as the first option. No mention of the consumer-facing team until the technical fix is done. No clear distinction between "the data was wrong on arrival" and "we processed correct data incorrectly".

### Q3 — Prevent and recover from duplication in a dbt foundation model

> *Peer engineer asks.* "You own an FDP table — a foundation customer model — built with dbt-bigquery as an incremental model. Two-part question. First: how do you design it so duplicates cannot survive a partial rerun? Second: imagine duplicates have leaked in anyway — twenty thousand rows over a week. How do you recover, in production, without taking the table offline?"

**Listening for, part one.** `unique_key` declared on the incremental model\index{dbt!unique\_key}, with `incremental_strategy='merge'`\index{dbt!merge strategy}. An explicit understanding of *why* merge is right here and append is wrong. Awareness that `unique_key` is a model-level setting, not a column-level one, and that getting the natural key wrong is the most common cause of duplication in dbt. A passing reference to dbt tests — `unique`, `not_null` — as a CI guardrail. Optionally: window-function dedupe (`row_number() over (partition by key order by updated_at desc)`) inside the model itself as a belt-and-braces layer.

**Listening for, part two.** A reversible recovery path. Build a candidate clean table in a separate dataset, validate row counts and checksums against expected, then atomically swap (rename, or `create or replace table` from select). Keep the original table around until the swap has been verified for at least a day. *Never* delete from a foundation table directly: the cure causes the next incident. A note that the same recovery script should be parameterised by date range so the next time this happens it is a five-minute job, not a four-hour scramble.

**Push on.** What does the table look like during the swap — is there a window where downstream queries see an empty or partial result? How does the audit trail know that twenty thousand rows were retired rather than processed? Would you do this differently if the table were a Type 2 SCD rather than a current-state model?

**Red flags.** `DELETE FROM` as the recovery plan. No backup of the dirty table. No verification step before the swap. Confusion between `unique_key` and a BigQuery primary-key constraint (BigQuery does not enforce primary keys — `unique_key` is a dbt-level convention).

### Q4 — dbt authentication across environments

> *Lead asks.* "Your dbt project runs in three environments — a developer's laptop, a shared dev project in CI, and production. Authentication is different in each. How do you actually wire it up so the same dbt code works everywhere, with no service-account JSON keys downloaded to anyone's machine?"

**Listening for.** `profiles.yml`\index{profiles.yml} with three targets — `dev_local`, `dev_ci`, `prod` — selected by an environment variable. On the laptop, **user OAuth** via `gcloud auth application-default login`; in CI, the GitHub Actions runner authenticates via **Workload Identity Federation**\index{Workload Identity Federation}; in both non-laptop cases, the configured target uses `impersonate_service_account`\index{dbt!impersonate\_service\_account} to assume a dbt-specific service account, with the human or runner identity holding `roles/iam.serviceAccountTokenCreator` on that SA. The production SA has tightly scoped BigQuery permissions and nothing else. A clear statement that nobody — *nobody* — downloads a JSON key.

**Push on.** How does a new developer get set up on day one? What permissions do they need in the dev project — exactly? How is the production SA permissioned compared to the dev SA, and why is the difference what it is? How would the team know if someone tried to bypass impersonation and authenticated with a downloaded key instead?

**Red flags.** "We put the JSON key in a `.env` file." "We share one developer SA across the team." Treating impersonation as something dbt does opaquely rather than as an explicit `profiles.yml` setting. Not knowing the difference between `roles/iam.serviceAccountUser` and `roles/iam.serviceAccountTokenCreator`.

### Q5 — Validate a long-lived consumable data product

> *Product owner asks, then pauses for one part at a time.*
>
> **Part A.** "Imagine we have built a bespoke consumable data product for a business team — let's say a unified customer view aggregated from four foundation tables. It has been live in production for six months. Tens of millions of rows, growing daily. How would you validate the *quality* of the data in that product, on an ongoing basis, while it is in production?"
>
> **Part B.** "Now a separate but related question. The product owner has signed off the field mapping — every column in the CDP came from a specific source field somewhere upstream. How would you validate, in production, that the *mapping* is correct — that each field in the CDP genuinely is the right field from the source, not just a plausible-looking value?"

**Listening for, Part A.** Continuous data-quality checks rather than one-shot validation. Row-count reconciliation against expected upstream volumes, day over day. Schema drift detection: nullability, type, cardinality of categorical fields. Distribution checks: anomaly detection on key business metrics (mean, p50, p95, count of distinct customers per day) versus a rolling baseline. Referential checks against the upstream foundation tables. A dashboard the product owner can actually look at, not just a CI test that fires once a release. A clear treatment of *test data versus production data* — the senior answer recognises that quality in a six-month-old production product cannot be assessed from synthetic fixtures. **You are listening for the phrase "live data", or its equivalent.** A junior engineer reaches for unit tests; a senior engineer reaches for sampled production data with PII handled carefully.

**Listening for, Part B.** This is the harder half, and the one that separates strong candidates. Mapping validation is not the same as quality validation — it asks whether the *plumbing* is right. The senior answer is: take a statistically meaningful sample of records from the CDP, trace each mapped field back to its claimed source, and *compare the live value in the CDP against the live value in the source table for the same record*. Anything else — schema docs, contract files, code review — only proves the mapping was *declared* correctly, not that the data actually flows through it correctly. Watch for the candidate to volunteer this phrasing — *use live data, compare against the source* — without prompting. That is the senior signal worth hiring on.

**Push on.** How big is "a statistically meaningful sample" here, and why? What do you do when the source field has been transformed (formatting, currency conversion, code lookup) before it lands in the CDP — does the comparison need to invert the transformation? How would you keep this check running on a schedule rather than as a one-off audit?

**Red flags.** "We have a contract file; that documents the mapping." "We write unit tests with synthetic data." Confusing data quality (is the value plausible?) with mapping correctness (is the value actually from the right source?). Not naming live production data as the source of truth.

### Q6 — CI/CD for a data system

> *Peer engineer asks.* "Sketch the CI/CD pipeline for the system we have been talking about — without referring to any specific tool stack unless I ask. What stages does it have, what does each stage gate, and what is the deploy unit?"

**Listening for.** A clean stage progression: format and lint, unit tests, integration tests against an emulator or short-lived test project, build the deploy artefact (Docker image, dbt manifest, library wheel), deploy to a non-production environment, run a smoke test there, then promote to production behind a manual gate or canary. A clear notion of *what gets versioned* — semantic version on libraries, immutable image tags on services, environment-specific configuration kept out of the artefact itself. A separation between *publishing* (a library reaches an artefact registry) and *deploying* (a running system picks up a new version). Authentication via Workload Identity Federation, not stored keys.

**Push on.** What makes you choose trunk-based development versus GitFlow for this kind of system, and why? Where does the rollback live — is it a redeploy of the previous tag, a feature flag, a schema migration that has been written reversibly? How does the pipeline behave differently for a documentation change versus a library change versus an infrastructure change — are all three really running the same workflow, or do you path-filter them? What stops someone pushing directly to main and bypassing the gates?

**Red flags.** "We deploy on every commit to main." (No, you do not — or you do, and you have an incident every Friday.) No distinction between publishing and deploying. No mention of how secrets reach the runner. Treating CI/CD as a single workflow file rather than a layered set of gates.

## Calibration notes

A few things worth saying explicitly before the panel runs the morning.

**Score concepts, not vocabulary.** A candidate who says "we'd use a load-then-promote pattern" and a candidate who says "we'd stage the file in raw, then transform into a curated table" have given the same answer. Mark both up. The interview is not a spelling test.

**Numbers are ballpark, not exam-question.** If you ask how big a Dataflow worker pool needs to be for 200 GB and the candidate says "twenty workers for two hours, maybe ten if I tune shuffle", that is a fine answer even if the truth on your specific platform is fifteen for an hour. They are showing they have a model; the model can be calibrated on day one.

**Time-box ruthlessly.** If a question is going badly at the seven-minute mark, move on with a soft reset ("let me take us to the next one"). The interview's job is to surface enough signal for a hire/no-hire call, not to be exhaustively complete.

**One panel, one bar.** Before the candidates arrive, the three interviewers agree what a passing answer looks like for each question. After both candidates have been through, the three of you score in private, then compare. The most common failure mode of unstructured panels is interviewers drifting to different bars without realising; pre-agreed rubrics prevent that.

**Read for the senior signal in Q5 explicitly.** That is the question this format is really designed around. Q1 to Q4 and Q6 establish that the candidate can do the work; Q5 establishes whether they can do it *with judgement*. If a candidate answers Part B without ever volunteering "use live data", they are not a no-hire — but they need the follow-up, and the score reflects that they needed it.

## What good looks like

A strong candidate, summarised: walks the ODP/FDP design without reaching for buzzwords; treats validation and reconciliation as built-in stages, not bolt-ons; defaults to reversible operations on production data; names `impersonate_service_account` without prompting; volunteers live-data comparison for mapping checks; distinguishes publish from deploy; pushes back on at least one of the panel's assumptions politely.

A weak candidate gives the right answers in vocabulary but cannot explain *why* underneath. Probe with "what would go wrong if we did the opposite" — the gap shows up immediately.

\begin{takeaways}
\textbf{Key takeaways}
\begin{itemize}
  \item Six questions, sixty minutes, three-person panel — enough breadth to cover ingestion, transformation, operations, security, data quality and process without rushing any single conversation.
  \item Q5 (the two-part long-lived-CDP scenario) is the senior-judgement question. The signal to listen for is the candidate volunteering \emph{live production data} as the source of truth for both quality and mapping checks.
  \item Score the concept, not the vocabulary. Two strong candidates can describe the same correct architecture in entirely different words.
  \item Calibrate before the candidates arrive: pre-agree the bar, pre-agree the rubric, pre-agree who leads what. Unstructured panels drift apart; structured panels converge.
  \item Reserve the last four minutes for the candidate's own questions, even when running over. Their questions are where they decide whether to accept your offer.
\end{itemize}
\end{takeaways}

\newpage

# Appendix F — Further Reading

Every framework rests on the shoulders of prior work. The patterns in this book didn't emerge from a vacuum: they were assembled from official documentation, a handful of essential books, and years of reading other people's post-incident write-ups at two in the morning. This appendix collects the resources I keep returning to — the ones that changed how I think, not just what I type. It's opinionated by design: where two resources cover the same ground, I've kept the one I'd reach for first.

## Google Cloud documentation that's actually useful

Most Cloud documentation is written for people who have never touched a computer. These are the exceptions.

The **Cloud Storage best practices guide** (`cloud.google.com/storage/docs/best-practices`) covers object naming for throughput, lifecycle rules, and retention policies — read it before you design your landing-zone layout, not after. The **BigQuery cost-control guide** (`cloud.google.com/bigquery/docs/best-practices-costs`) is the single most useful page in the entire BigQuery docs; the slot vs. on-demand decision alone is worth the ten minutes. The **Dataflow Flex Templates documentation** (`cloud.google.com/dataflow/docs/guides/templates/using-flex-templates`) explains the Docker-image packaging model clearly, including the metadata JSON schema that trips everyone up on first contact. The **Cloud Composer 2 architecture overview** (`cloud.google.com/composer/docs/composer-2/composer-versioning-overview`) is worth reading even if you decide not to use Composer — it explains the GKE-backed model and why the cost profile is what it is. The **Workload Identity Federation guide** (`cloud.google.com/iam/docs/workload-identity-federation`) is the authoritative reference for keyless authentication from GitHub Actions; don't let anyone on your team reach for a downloaded service-account key instead. Finally, the **IAM least-privilege patterns** section of the IAM best practices guide (`cloud.google.com/iam/docs/using-iam-securely`) is the page to send to colleagues who are still assigning `roles/editor` because it's easier.

## Apache Beam canon

The **Apache Beam programming guide** (beam.apache.org/documentation/programming-guide) is the starting point — it covers PCollections, transforms, windowing, and triggers more clearly than any third-party tutorial. Read it in order, at least once. The **streaming guide** (beam.apache.org/documentation/sdks/python-streaming) fills in what the programming guide elides about unbounded sources and watermarks; if you're doing anything with Pub/Sub you need both. The **I/O connectors catalogue** (beam.apache.org/documentation/io/built-in) saves you from reinventing connectors that already exist — check it before writing a custom source. Most important of all: *Streaming Systems* by Tyler Akidau, Slava Chernyak, and Reuven Lax (O'Reilly). Akidau led the Dataflow and Beam teams at Google and the book is the intellectual foundation for everything modern stream-processing is built on. If you're going to read one book about data pipelines that isn't this one, make it that one.

## dbt and analytics engineering

The **dbt Fundamentals course** (courses.getdbt.com) is free, takes a day, and is the fastest way to go from "I know SQL" to "I understand why dbt exists". Don't skip it on the grounds that you've already read the docs — the course gives you the mental model; the docs give you the API. The **dbt-bigquery adapter documentation** (docs.getdbt.com/docs/core/connect-data-platform/bigquery-setup) covers BigQuery-specific configuration: partitioning, clustering, job labels, and the service-account vs. OAuth credential decision. The **dbt Labs engineering blog** (getdbt.com/blog) publishes posts that are genuinely technical rather than marketing copy; the articles on incremental models and on testing strategy are particularly worth bookmarking. Coalesce — dbt Labs' annual conference — puts its talks on YouTube; the sessions from the past two years on multi-project mesh architecture and semantic layer are the clearest thinking available on where analytics engineering is heading. Tristan Handy's writing on the modern data stack (searchable on his Substack and older posts on getdbt.com) is worth reading for the framing — even where you disagree, it sharpens your own position.

## Apache Airflow

The **official Airflow documentation** (airflow.apache.org/docs) is dense but complete. The DAGs-as-code model, the executor options, and the XCom semantics are all explained there; the problem is knowing which sections matter. Marc Lamberti's **Complete Apache Airflow Training** (available via Udemy) is the fastest shortcut to productive with Airflow in a week — his examples are realistic and his explanations of the scheduler internals are the clearest I've found outside of reading the source code. Astronomer's blog on the **dbt-on-Airflow pattern** (astronomer.io/blog) covers the `BashOperator` vs. `DbtRunOperator` trade-off and the task-level retry semantics that catch people out when dbt models fail halfway through a DAG run. Finally, Maxime Beauchemin's 2016 article *The Rise of the Data Engineer* (searchable on Medium) is dated on tooling but still correct on the discipline — it's the text that named the role, and reading it explains why Airflow was designed the way it was.

## Mainframe modernisation

IBM's **Mainframe Modernization Reference Architecture** documentation is the canonical starting point for understanding what you're moving *from* — the LPAR model, the storage hierarchy, the batch-job scheduling assumptions. The **FINOS Open Mainframe Project** (openmainframeproject.org) hosts working groups and open-source tools aimed at exactly this migration space; the COBOL-to-cloud working group materials are useful even if you're not touching COBOL directly. For BigQuery migration patterns specifically, Mike Owens' writing on DB2-to-BigQuery migration (published across the Google Cloud blog and Medium) covers the schema-mapping decisions that cause the most pain: packed decimal fields, zone decimal, and null representation. Phil Wainewright's articles on EBCDIC handling — and specifically the character-set conversion edge cases that bite EBCDIC-to-UTF-8 migrations — are the most practical treatment I've found of a subject most documentation glosses over. If you're parsing mainframe copybooks programmatically, the *com.legstar* library documentation (legstar.com) is the reference you need; it's not glamorous, but it's the most complete treatment of COBOL record-layout parsing available in the open-source ecosystem.

## FinOps for data platforms

The **FinOps Foundation framework** (finops.org/framework) establishes the vocabulary and the crawl-walk-run maturity model that makes it possible to have a coherent conversation with finance teams about cloud spend. Start here if your organisation doesn't already have shared language. Google's **BigQuery cost-management whitepaper** (downloadable from cloud.google.com) goes deeper than the best-practices page listed above, covering reservation commitments, flex slots, and the capacity vs. on-demand modelling spreadsheet that engineering managers actually need. *Cloud FinOps* by J.R. Storment and Mike Fuller (O'Reilly, second edition) is the book that turned cost management from a niche concern into a discipline; the chapters on showback, chargeback, and anomaly detection are directly applicable to any team running data workloads at scale. The GCP documentation on **budget alerts and label-based cost attribution** (`cloud.google.com/billing/docs/how-to/budgets`) closes the loop between the theory and the implementation — labels on Dataflow jobs, Composer environments, and BigQuery reservations are how you turn the FinOps framework into actual line items on an invoice.

## Observability

*Observability Engineering* by Charity Majors, Liz Fong-Jones, and George Miranda (O'Reilly) is the book that finally articulated the difference between monitoring and observability in terms that change how you instrument code, not just how you think about it. Read Chapters 1 through 4 before you write your next structured log line. The **OpenTelemetry specification** (opentelemetry.io/docs/specs) is the reference for the semantic conventions that make traces and metrics portable across backends — knowing the spec is what lets you instrument a Beam pipeline in a way that works with both Google Cloud Trace and a future Grafana setup. The **Google SRE Books** — *Site Reliability Engineering* and *The Site Reliability Workbook* — are free online at sre.google and remain the most coherent treatment of reliability as an engineering discipline rather than an operations concern. *Distributed Tracing in Practice* by Austin Parker, Daniel Spoonhower, Jonathan Mace, Ben Sigelman, and Rebecca Isaacs (O'Reilly) bridges the gap between the OTel specification and the practical realities of instrumenting a multi-service pipeline — the chapter on sampling strategy is particularly useful.

## Software architecture and engineering culture

*Building Evolutionary Architectures* by Neal Ford, Rebecca Parsons, and Patrick Kua (O'Reilly) introduced the concept of fitness functions as architectural guardrails; it's the most useful framing for why the framework's structured tests exist as they do. *Accelerate* by Nicole Forsgren, Jez Humble, and Gene Kim (IT Revolution) provides the empirical basis for the deployment pipeline decisions in this book — if you need to justify trunk-based development and small, frequent releases to a sceptical stakeholder, the DORA metrics research it contains is your evidence. *A Philosophy of Software Design* by John Ousterhout (Yaknyam Press) is the book I wish I'd had in 2001; its treatment of deep vs. shallow modules is the clearest articulation I've read of why Culvert's decomposition into a thin contract core and swappable adapters lands where it does. *Domain-Driven Design Distilled* by Vaughn Vernon (Addison-Wesley) condenses the bounded-context thinking that informs how Culvert draws its contract and module boundaries.

## Communities worth lurking in

**r/dataengineering** on Reddit is noisy but has a high signal floor — the weekly "show and tell" threads aside, the technical questions surface real production problems. The **Apache Beam Slack** (the invite link is on beam.apache.org) has active channels where Beam committers answer questions; it's where I'd go before filing a JIRA. The **dbt Slack** (getdbt.com/community) is large and well-moderated; the `#troubleshooting` and `#best-practices` channels are genuinely useful. The **Apache Airflow Slack** mirrors that pattern. **Locally Optimistic** (locallyoptimistic.com) is a newsletter and Slack community aimed specifically at data practitioners inside companies rather than vendors selling to them — the perspective is refreshingly honest. **Data Engineering Weekly** (dataengineeringweekly.com) is a curated newsletter with a consistent editorial eye; Ananth Packkildurai's selection leans towards the architectural and the practical rather than the promotional. As for **Towards Data Science** on Medium: read it, but filter. The quality variance is extreme — treat it as a discovery mechanism, not a source of truth, and always verify anything operationally important against official documentation.

\newpage

# Colophon

This book was written in Markdown and rendered to PDF using Pandoc with the XeLaTeX engine. The body type is Georgia and code is set in Menlo. The cover was assembled with care; the copy was edited at the kitchen table.

The codebase described in this book is Culvert — a cloud-neutral, polyglot data-pipeline framework originating from the GCP reference implementation in this repository. It lives, at the time of writing, in the `culvert` repository; coordinated release to Maven Central (Java) and PyPI (`culvert`, Python) is forthcoming.

Errata, suggestions, and improvements are welcome.
