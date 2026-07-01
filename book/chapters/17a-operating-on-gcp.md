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
