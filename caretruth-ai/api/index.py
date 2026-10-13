import sys
from pathlib import Path

caretruth_dir = Path(__file__).resolve().parent.parent
if str(caretruth_dir) not in sys.path:
    sys.path.insert(0, str(caretruth_dir))

from api import app
