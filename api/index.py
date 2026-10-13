import sys
import importlib.util
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
caretruth_dir = root_dir / "caretruth-ai"

for p in (str(caretruth_dir), str(root_dir)):
    if p not in sys.path:
        sys.path.insert(0, p)

api_file = caretruth_dir / "api.py"
spec = importlib.util.spec_from_file_location("caretruth_api", api_file)
caretruth_module = importlib.util.module_from_spec(spec)
sys.modules["caretruth_api"] = caretruth_module
spec.loader.exec_module(caretruth_module)

app = caretruth_module.app
