"""PostgreSQL adapters for the Culvert data pipeline framework.

Today: :class:`PostgresStageClaim`, the Python side of the Java ``PostgresStageClaim``
(``data-pipeline-libraries-java/data-pipeline-postgres-java``), on the same tables.
"""

from data_pipeline_postgres.stage_claim import PostgresStageClaim, connect_from_environment

__all__ = ["PostgresStageClaim", "connect_from_environment"]
