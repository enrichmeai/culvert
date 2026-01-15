import sys
from pathlib import Path

# Add embedded libs to sys.path
PROJECT_ROOT = Path(__file__).parent.parent
LIBS_PATH = PROJECT_ROOT / "libs"

if LIBS_PATH.exists() and str(LIBS_PATH) not in sys.path:
    sys.path.insert(0, str(LIBS_PATH))
