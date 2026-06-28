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
