# File Archiving Standards

This document defines the standards for file archiving in the data platform.

## Path Conventions

### Standard Archive Path Structure

```
archive/{entity}/{year}/{month}/{day}/{filename}
```

Example:
```
archive/users/2025/12/31/users_export.csv
```

### Path Components

| Component | Format | Description |
|-----------|--------|-------------|
| `archive` | Static | Top-level archive directory |
| `entity` | lowercase | Data domain (e.g., users, orders, accounts) |
| `year` | YYYY | 4-digit year |
| `month` | MM | 2-digit month (01-12) |
| `day` | DD | 2-digit day (01-31) |
| `filename` | original | Original filename with extension |

### Entity Naming Standards

- Use lowercase
- Use underscores for multi-word names
- Be consistent across pipelines

| Entity Type | Example |
|-------------|---------|
| User data | `users` |
| Order data | `orders` |
| Account data | `accounts` |
| Audit logs | `audit_logs` |
| Transaction data | `transactions` |

## Policy Types

### Standard Daily (Default)

Use for: Regular operational data files

```yaml
name: "standard_daily"
pattern: "archive/{entity}/{year}/{month}/{day}/{filename}"
collision_strategy: "timestamp"
retention_days: 365
```

### Audit Logs

Use for: Compliance and audit trail files

```yaml
name: "audit_logs"
pattern: "archive/audit/{source}/{year}/{month}/{filename}"
collision_strategy: "uuid"
retention_days: 2555  # ~7 years
```

### Processing Cache

Use for: Temporary processing artifacts

```yaml
name: "processing_cache"
pattern: "archive/cache/{run_id}/{filename}"
collision_strategy: "version"
retention_days: 30
```

### Historical Archive

Use for: Long-term data retention

```yaml
name: "historical"
pattern: "archive/historical/{entity}/{year}/{filename}"
collision_strategy: "version"
retention_days: 3650  # 10 years
```

## Retention Policies

### Retention Categories

| Category | Days | Use Case |
|----------|------|----------|
| Short-term | 30 | Processing cache, temp files |
| Standard | 365 | Operational data |
| Compliance | 2555 | Audit logs, regulatory data |
| Historical | 3650 | Long-term archives |

### Retention Implementation

1. Files are tagged with archive timestamp
2. Retention is calculated from archive date
3. Cleanup runs periodically to remove expired files
4. Audit logs record all deletions

## Collision Handling

### When Collisions Occur

Collisions happen when:
- Same file archived twice in same day
- Reprocessing creates duplicate outputs
- Multiple pipeline runs in same time window

### Strategy Selection

| Strategy | Use When | Result |
|----------|----------|--------|
| `timestamp` | High-frequency files | `file_20251231_143022.csv` |
| `uuid` | Audit/unique tracking | `file_a1b2c3d4.csv` |
| `version` | Incremental updates | `file_v2.csv` |

### Recommended Strategies by Use Case

| Use Case | Strategy |
|----------|----------|
| Daily exports | timestamp |
| Audit logs | uuid |
| Report generations | version |
| Real-time data | timestamp |
| Incremental loads | version |

## Error Handling

### Error Path Structure

```
error/{timestamp}/{filename}
```

Example:
```
error/20251231_143022/bad_file.csv
```

### Error Categories

| Category | Action |
|----------|--------|
| Validation failure | Move to error bucket |
| Processing failure | Move to error bucket |
| Archive failure | Retry, then alert |
| Integrity failure | Move to error bucket |

### Error Retention

- Error files retained for 180 days
- Regular review process required
- Cleanup after investigation

## Audit Requirements

### Required Audit Fields

| Field | Description |
|-------|-------------|
| `source_path` | Original file location |
| `archive_path` | Archive destination |
| `archived_at` | Timestamp of archive |
| `file_size` | Size in bytes |
| `file_checksum` | MD5 hash |
| `status` | SUCCESS/FAILED |
| `operator` | User/service account |

### Audit Storage

- Audit logs stored in BigQuery
- 7-year retention minimum
- Queryable for compliance

## Naming Conventions

### File Names

- Use lowercase
- Use underscores for separators
- Include date if applicable
- Keep extensions consistent

| Good | Bad |
|------|-----|
| `users_2025_01_01.csv` | `Users 2025-01-01.CSV` |
| `order_export.csv` | `OrderExport.csv` |
| `daily_metrics.json` | `DailyMetrics (1).json` |

### Archive Buckets

| Environment | Bucket Name |
|-------------|-------------|
| Development | `{project}-archive-dev` |
| Staging | `{project}-archive-staging` |
| Production | `{project}-archive-prod` |

## Security Requirements

### Access Control

- Archive buckets: Read-only for most users
- Write access limited to service accounts
- Delete access limited to admin roles

### Encryption

- All files encrypted at rest (GCS default)
- Customer-managed keys for sensitive data
- No unencrypted file transfers

### Data Classification

| Classification | Archive Policy |
|----------------|----------------|
| Public | standard_daily |
| Internal | standard_daily |
| Confidential | audit_logs (with CMK) |
| Restricted | historical (with CMK) |

## Monitoring

### Key Metrics

| Metric | Alert Threshold |
|--------|-----------------|
| Archive failures | > 5 in 1 hour |
| Error bucket growth | > 100 files/day |
| Archive latency | > 30 seconds |
| Storage growth | > 10% week-over-week |

### Dashboard Components

1. Archive success rate (24h)
2. Files archived by entity
3. Error files pending review
4. Storage utilization
5. Retention compliance

## Compliance Checklist

- [ ] All files archived with audit trail
- [ ] Retention policies enforced
- [ ] Error files reviewed within SLA
- [ ] Access controls verified
- [ ] Encryption enabled
- [ ] Backup procedures documented
- [ ] DR tested quarterly

