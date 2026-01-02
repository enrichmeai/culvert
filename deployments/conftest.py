"""
Root conftest.py for blueprint - ensures proper import paths
"""
import sys
from pathlib import Path

# Add blueprint directory to path so imports work properly
blueprint_path = Path(__file__).parent
sys.path.insert(0, str(blueprint_path))
sys.path.insert(0, str(blueprint_path.parent))

# Make blueprint importable as a package

