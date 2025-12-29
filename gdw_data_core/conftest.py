"""
Root conftest.py for gdw_data_core - ensures proper import paths
"""
import sys
from pathlib import Path

# Add gdw_data_core directory to path so imports work properly
gdw_path = Path(__file__).parent
sys.path.insert(0, str(gdw_path))
sys.path.insert(0, str(gdw_path.parent))

# Make gdw_data_core importable as a package

