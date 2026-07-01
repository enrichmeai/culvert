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
