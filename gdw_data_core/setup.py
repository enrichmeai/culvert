from setuptools import setup, find_packages

setup(
    name="gdw-data-core",
    version="0.1.0",
    packages=find_packages(),
    package_dir={"": "."},
    install_requires=[
        "apache-beam[gcp]==2.49.0",
        "apache-airflow>=2.5.0,<2.8.0",
        "google-cloud-pubsub==2.18.0",
        "google-cloud-storage==2.10.0",
        "google-cloud-bigquery==3.12.0",
        "pydantic>=2.0.0,<3.0.0",
        "google-api-core==2.11.0",
    ],
    author="GDW Data Architect",
    description="Reusable framework for data migration pipelines",
)
