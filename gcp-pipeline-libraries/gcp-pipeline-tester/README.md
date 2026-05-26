# gcp-pipeline-tester (deprecated — see `data-pipeline-tester`)

This distribution is a thin deprecation shim for `data-pipeline-tester`. It exists only to keep existing `import gcp_pipeline_tester` statements working for one release cycle while consumers migrate.

## Migration

```python
# before
from gcp_pipeline_tester import BasePipelineTest
from gcp_pipeline_tester.builders import RecordBuilder
from gcp_pipeline_tester.mocks import BigQueryClientMock

# after — same surface, new package name
from data_pipeline_tester import BasePipelineTest
from data_pipeline_tester.builders import RecordBuilder
from data_pipeline_tester.mocks import BigQueryClientMock
```

Importing this package emits a `DeprecationWarning` and silently re-exports everything from `data_pipeline_tester`. No code changes are required if you can tolerate the warning, but new code should depend on `data-pipeline-tester` directly.

## Why the rename

The `gcp-pipeline-*` packages are evolving into a cloud-neutral framework called Culvert. The package convention is now `data-pipeline-*` (mirrors the `spring-data-*` naming used by the Java Spring framework). See `docs/framework-evolution/02-redesign.md` for the full rationale and the six-stage migration plan.

## Removal timeline

This shim will be removed once downstream consumers (deployments, CI workflows, internal projects) have migrated. There is no committed sunset date; the shim survives as long as removing it would break someone.

## See also

- [`data-pipeline-tester`](../../data-pipeline-libraries/data-pipeline-tester/) — the renamed successor
- [`docs/framework-evolution/02-redesign.md`](../../docs/framework-evolution/02-redesign.md) — Stage 1 redesign
