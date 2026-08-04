"""Launch bili2vrchat Flask app from src/."""
from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"

sys.path.insert(0, str(SRC_DIR))
os.chdir(ROOT_DIR)

if __name__ == "__main__":
    runpy.run_path(str(SRC_DIR / "app.py"), run_name="__main__")
