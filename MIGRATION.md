# Migration guide

Breaking changes between released versions, and what to do about them.

Culvert is pre-1.0, so [SemVer](https://semver.org/) permits breaking changes in
a minor bump. This file exists so "permitted" never means "unannounced".

---

## 0.1.x → 0.2.0

**One breaking change**, in both languages: `Warehouse.loadFromUri` now takes a
required `LoadOptions`.

### Why it changed

Before 0.2.0, `loadFromUri` had no way to say what should happen to data already
in the target table. Every backend was therefore free to pick, and picked
differently — the BigQuery adapter built a load job with only a schema and a
format, so BigQuery applied its own default of `WRITE_APPEND`.

The consequence: **re-running the same extract silently doubled the data.**
Nothing in the contract, the call site, or the job-control record recorded that
it had happened. The table just quietly held twice the rows.

There is deliberately **no** three-argument overload. A defaulted disposition is
exactly what caused the bug — it lets a caller write an idempotency-critical
load without ever deciding what a re-run means. Choosing is now a visible act at
every call site, which costs one argument and removes a class of silent data
corruption.

### Java

```java
// 0.1.x
long rows = warehouse.loadFromUri(uri, "proj.dataset.table", schema);

// 0.2.0 — pick the disposition that matches your table's semantics
long rows = warehouse.loadFromUri(uri, "proj.dataset.table", schema,
                                  LoadOptions.append());
```

`LoadOptions` lives in `com.enrichmeai.culvert.contracts`:

| Factory | Meaning |
| --- | --- |
| `LoadOptions.append()` | Add rows, keep what is there. **The 0.1.x behaviour** — use this to preserve existing semantics exactly. |
| `LoadOptions.truncate()` | Replace the whole target table. |
| `LoadOptions.truncatePartition("20260601")` | Replace one partition. BigQuery partition-decorator form. |
| `LoadOptions.errorIfExists()` | Load only into an empty target; fail otherwise. |

**If you only want to compile again, pass `LoadOptions.append()`** — that is
byte-for-byte the old behaviour. But if the load is a re-runnable batch extract,
append is probably not what you want; see *Choosing a disposition* below.

### Python

```python
# 0.1.x
n = warehouse.load_from_uri(uri, "proj.dataset.table", schema)

# 0.2.0
from data_pipeline_core.contracts import LoadOptions, WriteDisposition
n = warehouse.load_from_uri(uri, "proj.dataset.table", schema,
                            options=LoadOptions.append())
```

`LoadOptions` and `WriteDisposition` are exported from
`data_pipeline_core.contracts`. The factories mirror Java:
`LoadOptions.append()`, `.truncate()`, `.truncate_partition(id)`,
`.error_if_exists()`.

### If you implement `Warehouse` yourself

Add the parameter, and **honour it or throw** — never silently downgrade to
append. A caller who asked for replace and got append ends up with duplicated
data and no signal, which is the failure this parameter exists to prevent.

Backends that cannot express a disposition must raise, naming it. The shipped
`AthenaWarehouse` does this: its load idiom is `INSERT INTO`, and Athena has no
DML on non-Iceberg tables, so it refuses anything but `APPEND` rather than
pretending.

If you extend `WarehouseContractTest`, two new hooks are available. Both have
safe defaults, so an existing subclass keeps compiling:

- `unsupportedDispositions()` — declare what your backend refuses. The suite
  then asserts it *throws* for those, rather than appending silently.
- `loadUri()` — a URI in your backend's scheme, used only for argument
  validation.

### Choosing a disposition

Partition-scoped replace only helps when the table is partitioned by the column
that identifies a load — usually an extract or ingestion date. A table
partitioned on a **business** date cannot express "replace this extract" as a
partition operation at all, because one extract spans many business dates.

The Culvert reference ODP tables are exactly this case: `odp_generic.customers`
partitions on `created_date`, `odp_generic.accounts` on `open_date`. They
achieve idempotency by deleting the extract's rows and then appending, not by
partition replace. Pick the mechanism that matches your table; do not assume
`truncate()` plus a partition is always available.

### Not breaking, but worth knowing

- **Java toolchain.** The reactor now builds on JDK 21 and JDK 25. If you were
  pinned below 21 for Mockito reasons, that constraint is gone.
- **`data-pipeline-libraries/*` distribution versions** moved from `0.1.0` to
  the 0.2.0 line. These are packaged inside the single `culvert` wheel and were
  never published separately, so this affects editable installs from the repo
  only.

---

## Reporting a migration problem

If a change here broke you and this guide does not cover it, open a GitHub issue
— that is a documentation defect, not user error.
