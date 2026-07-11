# Why is there no Spring for data pipelines?

*Twenty-five years of building the same scaffolding on every platform, and the question that finally made me stop.*

---

I have been shipping software for twenty-five years, and for most of that time the platforms would not sit still. Oracle SOA Suite. JBoss. WebLogic. Spring. Dropwizard. Kubernetes. AWS. GCP. Every few years the ground moved, and every few years I rebuilt the same things on top of it: audit trails, cost tracking, error classification, schema drift handling, reconciliation. The hard parts never changed. Only the logos did.

Around year fifteen I noticed something embarrassing: every data team I joined was rebuilding the same scaffolding, and none of us called it that. We called it "the platform", or "the framework", or — my favourite — "utils". Different company, different cloud, same six months of building the unglamorous machinery that makes a pipeline trustworthy rather than merely functional.

Then I would look across at my colleagues writing ordinary backend services, and they did not have this problem. They had Spring.

## What Spring actually got right

It is easy to forget what the JVM world looked like before Spring, so let me remind you: it looked like data engineering today. Every company had its own way of wiring components together, its own transaction handling, its own configuration story. Portability between application servers was a slideware promise.

Spring's insight was not dependency injection, whatever the interview questions say. Spring's insight was that **a small, honest core of contracts could stay stable while everything around it stayed swappable**. `DataSource` doesn't care which database you use. `PlatformTransactionManager` doesn't care who commits. When MongoDB arrived years later, `spring-data-mongodb` slotted in beside JPA without a single existing application changing a line. The core had drawn the portability boundary in the right place, and an entire ecosystem grew on top of it.

Now name the equivalent for data pipelines.

You can't, because it doesn't exist. We have magnificent *engines* — Beam for execution, Airflow for orchestration, dbt for transformation. But engines are not frameworks. Nobody has drawn the boundary that says: *this* part of your pipeline is about data engineering, and *that* part is about the cloud you happen to be renting this year.

## The ninth gap

Teams that get serious about data infrastructure eventually build an internal framework. I have watched it happen — and done it — several times. The framework solves the real gaps: auditability, data quality, job control, cost visibility, lineage. And it embeds the cloud's fingerprints at every layer while doing so. The schema validator calls BigQuery directly. The cost tracker has Dataflow slot prices as module-level constants. The audit publisher is hard-wired to Pub/Sub.

Nobody decides this. It happens because the project is on GCP, the engineers know GCP, and there is no reason — on any individual Tuesday — to do otherwise. The cloud-specific assumptions are not design choices; they are habits.

I know because I built exactly that framework. Years of production hardening, all the gaps closed, genuinely good software — and when I finally audited it honestly, I found something that changed how I think about this whole problem: **most of the code was already cloud-neutral. It just didn't know it.** The audit trails, the reconciliation logic, the quality scoring, the job-state machine — none of it had any business knowing which cloud it ran on. The GCP parts were a thin layer on the outside.

But thin layers that are not *identified* as thin layers become load-bearing walls. When someone asks "could we run this on AWS?", the honest answer is a rewrite — not because the code is cloud-specific, but because nobody ever said out loud which parts weren't.

That is the ninth gap. The frameworks we build solve auditability and quality and cost, and then create a portability problem that none of the engines above them can solve, because the problem lives in *our* code, not theirs.

## What the boundary looks like

The fix is not "abstract everything", which is how you get frameworks nobody can debug. The fix is Spring's fix: a deliberately small set of contracts at exactly the seam where data engineering ends and cloud vendoring begins.

A `BlobStore` is eight operations on bytes and URIs. It does not mention buckets, containers, or eventual consistency. A `Warehouse` covers what any serious analytical store supports — load, query, table existence — and nothing more; the clustering tricks stay in the BigQuery adapter where they belong. A `JobControlRepository` records what ran and what happened, and could not care less whether that record lives in BigQuery or DynamoDB. (Interestingly, when I implemented both, DynamoDB turned out to be *better* at it — conditional writes give you an atomic control plane BigQuery structurally can't. You only learn that when a contract forces the comparison.)

Sixteen interfaces, in my current counting. Business logic depends on the contracts. Adapters implement them per cloud. Conformance is enforced by a shared test suite every adapter must pass — because an interface without enforcement is documentation, and documentation drifts.

And the payoff isn't only cross-*cloud*. The same seam is what lets a pipeline run against emulators on your laptop, against a dev project from your laptop, and against production from CI — same business logic, different wiring at the edge. The developers-run-everything-locally experience that made Spring pleasant to live with falls out of the same boundary.

## Someone should build this

For the last while I have been building it, in the open — contracts first, Java and Python implementations, GCP as the first cloud (a concrete target keeps you honest), AWS as the proof the seam is real. The repository is public, the mistakes are in the commit history, and the framework is called Culvert — the unglamorous pipe under the road that just works, which is the whole ambition.

I am not here to sell it to you today; nothing is published yet, and I have strong opinions about not announcing things that haven't survived a real deployment. (That story — what happened when eleven hundred green tests met an actual cloud project — is the next article, and it is humbling.)

I am here for the argument: **data engineering deserves its Spring.** A small honest core, swappable cloud modules, contracts enforced by tests rather than intentions. Twenty-five years of rebuilt scaffolding says the demand is there.

If you have built one of these internal frameworks — or are trapped inside one — I would genuinely like to hear what your version of the ninth gap looks like.

---

*Joseph Aruja has spent 25 years building software for banks and enterprises, and too much of it was the same software. Culvert is being built in the open at [github.com/enrichmeai/culvert](https://github.com/enrichmeai/culvert).*
