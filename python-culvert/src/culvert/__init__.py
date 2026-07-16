"""Culvert — a cloud-agnostic, polyglot data-pipeline framework.

One language-neutral contract set (Source, Sink, Transform, Pipeline,
RuntimeContext, BlobStore, Warehouse, JobControlRepository, ...), realised in
Java and Python, with cloud specifics behind adapters. This distribution is the
Python side; the Java twin ships as ``com.enrichmeai.culvert:*`` on Maven
Central.

For 0.1.0 the import packages keep their library names — start at
``data_pipeline_core`` for the contracts::

    from data_pipeline_core import autoconfig
    from data_pipeline_core.contracts.blob_store import BlobStore

Install extras for the adapters you need::

    pip install culvert[gcp]            # BigQuery, GCS, Pub/Sub, Secret Manager, observability
    pip install culvert[orchestration]  # Airflow-side DAG factory, operators, sensors
    pip install culvert[transform]      # dbt runner assets
    pip install culvert[all]

Docs and worked examples: https://github.com/enrichmeai/culvert
"""

__version__ = "0.2.0.dev0"

__all__ = ["__version__"]
