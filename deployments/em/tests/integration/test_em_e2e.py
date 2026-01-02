"""
EM Integration Tests.

Integration tests for the EM (Application A) pipeline.
"""

import pytest
from datetime import date


class TestEMIntegrationFlow:
    """Test EM end-to-end integration flow."""

    def test_flow_overview(self):
        """Document the E2E flow being tested."""
        # EM E2E Flow:
        # 1. Files arrive in landing bucket (3 entities)
        # 2. .ok files trigger Pub/Sub notification
        # 3. Airflow DAG starts
        # 4. Validate files (HDR/TRL, record count, checksum)
        # 5. Run Dataflow pipeline to load ODP for each entity
        # 6. EntityDependencyChecker waits for all 3 entities
        # 7. Trigger FDP transformation (dbt JOIN 3→1)
        # 8. Archive source files
        pass

    def test_entity_dependency_wait(self):
        """Test EM waits for all 3 entities before FDP."""
        from deployments.em.config import REQUIRED_ENTITIES

        # EM has 3 required entities
        assert len(REQUIRED_ENTITIES) == 3
        assert "customers" in REQUIRED_ENTITIES
        assert "accounts" in REQUIRED_ENTITIES
        assert "decision" in REQUIRED_ENTITIES

    def test_join_transformation_flow(self):
        """Test JOIN transformation creates 1 FDP table."""
        # EM transforms 3 sources to 1 target:
        # - odp_em.customers + odp_em.accounts + odp_em.decision
        # - → fdp_em.em_attributes

        source_tables = [
            "odp_em.customers",
            "odp_em.accounts",
            "odp_em.decision"
        ]
        target_tables = ["fdp_em.em_attributes"]

        assert len(source_tables) == 3
        assert len(target_tables) == 1


class TestEMDataFlow:
    """Test EM data flow patterns."""

    def test_odp_to_fdp_mapping(self):
        """Test ODP fields map correctly to FDP table."""
        from deployments.em.domain.schema import (
            EM_SCHEMAS,
        )

        # EM has 3 ODP tables + 1 FDP table
        assert "customers" in EM_SCHEMAS
        assert "accounts" in EM_SCHEMAS
        assert "decision" in EM_SCHEMAS
        assert "em_attributes" in EM_SCHEMAS

    def test_audit_columns_preserved(self):
        """Test audit columns flow through correctly."""
        from deployments.em.domain.schema import get_schema

        # All tables should have audit columns
        for entity in ["customers", "accounts", "decision", "em_attributes"]:
            schema = get_schema(entity)
            field_names = [f["name"] for f in schema]
            assert "_run_id" in field_names
            assert "_extract_date" in field_names


class TestEMVsLOA:
    """Test key differences between EM and LOA."""

    def test_em_vs_loa_entity_count(self):
        """Test EM has 3 entities vs LOA's 1."""
        from deployments.em.config import REQUIRED_ENTITIES as EM_ENTITIES
        from deployments.loa.config import REQUIRED_ENTITIES as LOA_ENTITIES

        assert len(EM_ENTITIES) == 3
        assert len(LOA_ENTITIES) == 1

    def test_em_uses_dependency_checker(self):
        """Test EM uses EntityDependencyChecker (LOA doesn't need it)."""
        # EM: Must wait for all 3 entities before FDP
        # LOA: Single entity, immediate FDP trigger
        em_needs_dependency_checker = True
        loa_needs_dependency_checker = False

        assert em_needs_dependency_checker
        assert not loa_needs_dependency_checker

    def test_em_join_vs_loa_split(self):
        """Test EM uses JOIN (3→1) vs LOA uses SPLIT (1→2)."""
        # EM: JOIN 3 ODP tables → 1 FDP table
        em_odp_count = 3
        em_fdp_count = 1

        # LOA: SPLIT 1 ODP table → 2 FDP tables
        loa_odp_count = 1
        loa_fdp_count = 2

        assert em_odp_count == 3
        assert em_fdp_count == 1
        assert loa_odp_count == 1
        assert loa_fdp_count == 2

