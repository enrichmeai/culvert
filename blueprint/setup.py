#!/usr/bin/env python3
"""
LOA Blueprint - Python Package Setup
Enables: pip install -e . (development) or pip install . (production)
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README for long description
readme_file = Path(__file__).parent / "README.md"
long_description = ""
if readme_file.exists():
    long_description = readme_file.read_text(encoding="utf-8")

# Read requirements from requirements.txt
requirements_file = Path(__file__).parent / "setup/requirements.txt"
install_requires = []
if requirements_file.exists():
    with open(requirements_file, "r") as f:
        install_requires = [
            line.strip()
            for line in f.readlines()
            if line.strip() and not line.startswith("#") and not line.startswith("-r")
        ]

# Read development requirements
dev_requirements_file = Path(__file__).parent / "setup/requirements-dev.txt"
extras_require = {}
if dev_requirements_file.exists():
    with open(dev_requirements_file, "r") as f:
        dev_requires = [
            line.strip()
            for line in f.readlines()
            if line.strip() and not line.startswith("#") and not line.startswith("-r")
        ]
        extras_require["dev"] = dev_requires

setup(
    name="loa-blueprint",
    version="1.0.0",
    description="LOA Blueprint - Mainframe to GCP Migration Framework",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Data Engineering Team",
    author_email="data-eng@company.com",
    url="https://github.com/company/loa-blueprint",
    project_urls={
        "Documentation": "https://github.com/company/loa-blueprint/blob/main/docs/",
        "Source Code": "https://github.com/company/loa-blueprint",
        "Issue Tracker": "https://github.com/company/loa-blueprint/issues",
    },
    license="Proprietary",
    python_requires=">=3.9",
    package_dir={"": "."},
    packages=find_packages(where="."),
    install_requires=install_requires,
    extras_require=extras_require,
    entry_points={
        "console_scripts": [
            "loa-pipeline=blueprint.cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "License :: Other/Proprietary License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: System :: Archiving",
        "Topic :: System :: Distributed Computing",
    ],
    keywords=[
        "migration",
        "mainframe",
        "gcp",
        "google-cloud",
        "data-pipeline",
        "etl",
        "beam",
        "bigquery",
    ],
    include_package_data=True,
    zip_safe=False,
)

