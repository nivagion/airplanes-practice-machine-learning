"""Rebuild prepared data and the portable viewer from the downloaded source."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from approach.dataset import build_dataset
from approach.viewer import build_viewer

if __name__ == "__main__":
    build_dataset(ROOT)
    build_viewer(ROOT)
    print(f"Ready: {ROOT / 'prepared/viewer.html'}")
