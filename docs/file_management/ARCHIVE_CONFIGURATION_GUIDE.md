# Archive Configuration Guide

This guide explains how to configure the Archive Policy Engine for file management.

## Configuration File Structure

The archive configuration is stored in a YAML file (typically `archive_config.yaml`).

### Basic Structure

```yaml
# Archive policies define how files should be archived
archive_policies:
  - name: "policy_name"
    description: "Policy description"
    pattern: "archive/{entity}/{year}/{month}/{day}/{filename}"
    collision_strategy: "timestamp"
    retention_days: 365
    enabled: true

# Default policy when no policy is specified
default_policy: "standard_daily"
```

## Policy Configuration

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Unique policy identifier |
| `pattern` | string | Archive path template with placeholders |
| `collision_strategy` | string | How to handle duplicate files |

### Optional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `description` | string | "" | Human-readable description |
| `retention_days` | int | 365 | Days to retain archived files |
| `enabled` | bool | true | Whether policy is active |

## Template Variables

Use these placeholders in your pattern:

| Variable | Description | Example |
|----------|-------------|---------|
| `{entity}` | Data entity/domain | `users`, `orders` |
| `{year}` | 4-digit year | `2025` |
| `{month}` | 2-digit month | `01`, `12` |
| `{day}` | 2-digit day | `01`, `31` |
| `{filename}` | Original filename with extension | `data.csv` |
| `{basename}` | Filename without extension | `data` |
| `{ext}` | File extension with dot | `.csv` |
| `{run_id}` | Processing run identifier | `run_12345` |
| `{source}` | Source system identifier | `mainframe` |

### Example Patterns

```yaml
# Daily organization
pattern: "archive/{entity}/{year}/{month}/{day}/{filename}"
# Result: archive/users/2025/12/31/users.csv

# Source system organization
pattern: "archive/{source}/{entity}/{year}/{filename}"
# Result: archive/mainframe/accounts/2025/accounts.csv

# Run-based organization
pattern: "archive/runs/{run_id}/{entity}/{filename}"
# Result: archive/runs/run_12345/users/users.csv
```

## Collision Strategies

When a file already exists at the target path, the collision strategy determines how to handle it.

### Timestamp Strategy

Appends current timestamp to filename.

```yaml
collision_strategy: "timestamp"
# Original: archive/users/2025/12/31/data.csv
# Result:   archive/users/2025/12/31/data_20251231_143022.csv
```

### UUID Strategy

Appends short UUID to filename.

```yaml
collision_strategy: "uuid"
# Original: archive/users/2025/12/31/data.csv
# Result:   archive/users/2025/12/31/data_a1b2c3d4.csv
```

### Version Strategy

Appends incrementing version number.

```yaml
collision_strategy: "version"
# First collision:  archive/users/data_v1.csv
# Second collision: archive/users/data_v2.csv
# Third collision:  archive/users/data_v3.csv
```

## Complete Configuration Example

```yaml
# archive_config.yaml

archive_policies:
  # Standard daily archiving for most data
  - name: "standard_daily"
    description: "Standard daily archiving with date-based path"
    pattern: "archive/{entity}/{year}/{month}/{day}/{filename}"
    collision_strategy: "timestamp"
    retention_days: 365
    enabled: true

  # Audit logs with extended retention
  - name: "audit_logs"
    description: "Audit logs with 7-year retention"
    pattern: "archive/audit/{source}/{year}/{month}/{filename}"
    collision_strategy: "uuid"
    retention_days: 2555
    enabled: true

  # Temporary processing files
  - name: "processing_cache"
    description: "Short-term processing cache"
    pattern: "archive/cache/{run_id}/{filename}"
    collision_strategy: "version"
    retention_days: 30
    enabled: true

  # Historical data archive
  - name: "historical"
    description: "Long-term historical archive"
    pattern: "archive/historical/{entity}/{year}/{filename}"
    collision_strategy: "version"
    retention_days: 3650
    enabled: true

default_policy: "standard_daily"
```

## Using the Configuration

### Loading from File

```python
from gdw_data_core.core.file_management.policy import ArchivePolicyEngine

# Load from YAML file
engine = ArchivePolicyEngine(config_path="config/archive_config.yaml")
```

### Loading from Dictionary

```python
config = {
    'archive_policies': [
        {
            'name': 'standard_daily',
            'pattern': 'archive/{entity}/{year}/{month}/{day}/{filename}',
            'collision_strategy': 'timestamp',
            'enabled': True
        }
    ],
    'default_policy': 'standard_daily'
}

engine = ArchivePolicyEngine(config_dict=config)
```

### Resolving Paths

```python
# Basic resolution
path = engine.resolve_path(
    source_path="landing/users.csv",
    entity="users"
)
# Result: archive/users/2025/12/31/users.csv

# With specific date
path = engine.resolve_path(
    source_path="landing/orders.csv",
    entity="orders",
    year=2025,
    month=6,
    day=15
)
# Result: archive/orders/2025/06/15/orders.csv

# With collision detection
existing_paths = ["archive/users/2025/12/31/users.csv"]
path = engine.resolve_path(
    source_path="landing/users.csv",
    entity="users",
    existing_paths=existing_paths
)
# Result: archive/users/2025/12/31/users_20251231_143022.csv
```

## Best Practices

1. **Use descriptive policy names** - Names should clearly indicate the purpose
2. **Document retention requirements** - Set `retention_days` based on compliance needs
3. **Use appropriate collision strategies**:
   - `timestamp` for high-frequency files (prevents data loss)
   - `uuid` for audit logs (guaranteed uniqueness)
   - `version` for incremental updates (easy to track versions)
4. **Include entity in path** - Enables easy querying by data domain
5. **Include date components** - Facilitates time-based cleanup and querying
6. **Test policies before production** - Use the policy engine's `resolve_path` to verify patterns

## Validation

The policy engine validates configurations on load:

```python
# Check if policy exists and is enabled
is_valid = engine.validate_policy("standard_daily")

# Get all policy names
names = engine.list_policy_names()

# Get all policies
policies = engine.get_policies()
```

## Error Handling

```python
from gdw_data_core.core.file_management.policy import ArchivePolicyEngine

try:
    engine = ArchivePolicyEngine(config_path="missing.yaml")
except FileNotFoundError:
    print("Configuration file not found")

try:
    policy = engine.get_policy("nonexistent")
except ValueError as e:
    print(f"Policy error: {e}")
```

