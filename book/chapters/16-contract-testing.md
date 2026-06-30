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
