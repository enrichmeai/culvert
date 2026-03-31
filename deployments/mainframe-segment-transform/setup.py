"""Minimal setup.py for Dataflow worker package installation."""
import setuptools

setuptools.setup(
    name='segment-transform',
    version='1.0.0',
    packages=setuptools.find_packages(where='src'),
    package_dir={'': 'src'},
    install_requires=[
        'pyyaml>=6.0',
        'gcp-pipeline-framework==1.0.29',
    ],
    package_data={'': ['*.yaml']},
)
