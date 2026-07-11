# 1,145 green tests. The first real deploy failed 8 different ways.

*What a £2 cloud bill taught me that a year of test suites couldn't.*

---

I want to tell you about the most valuable £2 I have spent in twenty-five years of software.

The setup: I have been building a data-pipeline framework in the open — contracts in the core, cloud adapters at the edge, Java and Python. By early July it had 1,145 passing tests. Unit tests, integration tests against Google Cloud emulators, integration tests against LocalStack for the AWS adapters, contract-conformance suites that every adapter must pass. The kind of coverage you put in a conference talk.

Then I deployed it to a real Google Cloud project for the first time, dropped one CSV file into a bucket, and watched it fail.

Then I fixed that and watched it fail differently. Eight times.

Not one of those eight failures had been visible to the test suite. Every single one was invisible *by construction* — and that is the interesting part, because the classes of bug that only surface on a real deployment are predictable, and most teams' test strategies (including, evidently, mine) are structurally blind to all of them.

## The eight failures

**1. The jar that wouldn't start.** The Maven Shade configuration set the main class as a bare config child instead of inside a `ManifestResourceTransformer` — a one-line mistake that produces a fat jar with no `Main-Class`. `java -jar` fails instantly. No test caught it because tests run classes, not jars. The artefact you ship is not the code you test.

**2. The architectural one.** Apache Beam serialises your pipeline to workers — even the "local" DirectRunner does, deliberately, to catch exactly this. My framework's runtime context keeps its adapter registry `transient` and rebuilds it on the worker via ServiceLoader discovery. Except the BigQuery adapters needed constructor arguments, so ServiceLoader silently skipped them, so the worker threw `No implementation registered for Warehouse` on the very first element. Every local test had injected adapters as plain fields — never once crossing the serialisation boundary the framework itself documents. The fix (self-configuring constructors reading worker environment) was in the code as a TODO. Written by me, months earlier, describing precisely this failure.

**3. IAM, part one.** The pipeline's service account had dataset-level write permission but not project-level `bigquery.jobUser` — it could edit data but not *run jobs*. Emulators do not do IAM. Production does nothing but.

**4. Schema drift, part one.** The Terraform that provisioned the job-control table carried an old column layout; the code inserting into it had evolved. `Column pipeline_name is not present`. Two artefacts, both version-controlled, both individually reviewed, never once tested *against each other* — because the tests used H2 and the emulator, and both were set up by the code, not by the Terraform.

**5. The container that couldn't be built.** The dbt runner's Dockerfile installed our transform library from local source — but not the core library it depends on, because nothing is on PyPI yet. Local dev environments had it installed already. Clean cloud builds start from nothing, and nothing is where dependency lies get exposed.

**6. The template that didn't render.** dbt project variables in `dbt_project.yml` are not Jinja-rendered — a fact I half-knew and fully forgot. The literal string `{{ env_var('GCP_PROJECT_ID') }}` arrived in BigQuery as a project identifier. BigQuery was unimpressed.

**7. IAM, part two.** dbt's custom schemas mean it creates datasets at runtime. Dataset-scoped permissions can't create datasets. Same lesson as #3, one layer up — least-privilege IAM is itself a system you have to test.

**8. The phantom column.** The consumption-layer dbt model selected `facility_key` from an upstream table whose producing model had never emitted such a column. Two deployments, each with passing tests against its *own* fixtures, each certain about a contract that existed only in fixtures. Only running the real chain — ingest, then transform, then consume, same warehouse — exposed that the handshake was imaginary.

## The pattern

Look at the list again. It is not eight random bugs. It is four categories, and none of them live where unit tests look:

- **Artefact packaging** (1, 5): you test code; you ship jars and containers.
- **Serialisation and process boundaries** (2): frameworks that ship work to workers have a second startup path, and it is the one your tests bypass.
- **Identity and permissions** (3, 7): emulators are anarchists; production is a bureaucracy.
- **Cross-artefact contracts** (4, 6, 8): schema in Terraform vs schema in code; fixtures in one repo vs reality in another; template engines that render some files and not others.

Every one of these is a *seam between things that are tested separately*. The unit suite was not wrong — every green test was telling the truth about its own little world. The lie was in the gaps between the worlds.

## The £2 gate

Here is what it cost to find all eight: one Google Cloud project, Cloud Run jobs that scale to zero, BigQuery and Pub/Sub inside the free tier, a few container builds. Under £2. No Kubernetes cluster, no standing orchestrator, nothing left running overnight. (The event-driven version — file lands, Eventarc fires, Workflows runs the ingestion job, then the transforms — costs effectively nothing at rest.)

That is the actual lesson, and it is the policy I have now written into the project's release gate: **green tests earn you a deployment, not a release.** Nothing gets published — not the libraries, not the book I am writing about them, nothing — until the reference deployments have run end-to-end on a real cloud project and the bugs that only reality can catch have been caught. The gate costs £2 and a day. Bug #2 alone — shipped to users — would have cost the project its credibility in week one.

I used to read "works on my machine" as a joke about junior developers. I now read it as a precise technical description of what a test suite is: your machine, formalised. The other machine — the one with IAM and cold starts and serialisation boundaries and the Terraform nobody ran — has to be visited in person.

Eleven hundred green tests, and the most important quality signal of the year was a £2 bill and a stack trace.

---

*This is part of a series about building Culvert, a cloud-agnostic data-pipeline framework, in the open: [github.com/enrichmeai/culvert](https://github.com/enrichmeai/culvert). The previous article asked why data engineering never got its Spring.*
