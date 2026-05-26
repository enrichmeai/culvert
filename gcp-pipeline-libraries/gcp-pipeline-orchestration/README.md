# gcp-pipeline-orchestration (deprecated — see `data-pipeline-orchestration`)

This distribution is a thin deprecation shim for `data-pipeline-orchestration`. It exists only to keep existing `import gcp_pipeline_orchestration` statements working for one release cycle while consumers migrate.

## Migration

```python
# before
from gcp_pipeline_orchestration import ...

# after
from data_pipeline_orchestration import ...
```

Importing this package emits a `DeprecationWarning` and silently re-exports everything from `data_pipeline_orchestration`. No code changes are required if you can tolerate the warning, but new code should depend on `data-pipeline-orchestration` directly.

## Why the rename

The `gcp-pipeline-*` packages are evolving into a cloud-neutral framework called Culvert. The package convention is now `data-pipeline-*` (mirrors the `spring-data-*` naming used by the Java Spring framework). See `docs/framework-evolution/02-redesign.md` for the full rationale and the six-stage migration plan.

## Removal timeline

This shim will be removed once downstream consumers (deployments, CI workflows, internal projects) have migrated. There is no committed sunset date; the shim survives as long as removing it would break someone.

## See also

- [`data-pipeline-orchestration`](../../data-pipeline-libraries/data-pipeline-orchestration/) — the renamed successor
- [`docs/framework-evolution/02-redesign.md`](../../docs/framework-evolution/02-redesign.md) — Stage 1 redesign
