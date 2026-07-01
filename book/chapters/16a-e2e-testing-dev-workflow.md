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
