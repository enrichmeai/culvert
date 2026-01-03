"""
EM (Application A) Deployment.

Complete data migration pipeline for EM system.

Structure:
- config/: System configuration (IDs, datasets, paths)
- schema/: Entity schemas (Customers, Accounts, Decision)
- validation/: File and record validation
- pipeline/: Dataflow pipeline implementation
- orchestration/: Airflow DAGs
- transformations/: dbt models
- tests/: Unit and integration tests

EM System:
- 3 source entities: Customers, Accounts, Decision
- 3 ODP tables: odp_em.customers, odp_em.accounts, odp_em.decision
- 1 FDP table: fdp_em.em_attributes (JOIN of 3 sources)
- Dependency: Wait for all 3 entities before FDP transformation
"""

from .config import (
    SYSTEM_ID,
    REQUIRED_ENTITIES,
    ODP_DATASET,
    FDP_DATASET,
)
from .schema import (
    EMCustomerSchema,
    EMAccountSchema,
    EMDecisionSchema,
    EM_SCHEMAS,
    get_em_schema,
)
from .validation import (
    EMValidator,
    ValidationResult,
)

__all__ = [
    # Config
    'SYSTEM_ID',
    'REQUIRED_ENTITIES',
    'ODP_DATASET',
    'FDP_DATASET',
    # Schemas
    'EMCustomerSchema',
    'EMAccountSchema',
    'EMDecisionSchema',
    'EM_SCHEMAS',
    'get_em_schema',
    # Validation
    'EMValidator',
    'ValidationResult',
]
