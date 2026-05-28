import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
os.environ.setdefault("GOOGLE_API_KEY", "dummy-key-for-tests")
