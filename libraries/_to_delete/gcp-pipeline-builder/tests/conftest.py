"""
Root conftest.py for gcp-pipeline-builder - ensures proper import paths
"""
import sys
from pathlib import Path

# Add src directory to path so imports work properly
root_path = Path(__file__).parent.parent
src_path = root_path / "src"
sys.path.insert(0, str(src_path))
sys.path.insert(0, str(root_path))
