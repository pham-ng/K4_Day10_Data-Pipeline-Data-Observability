from __future__ import annotations

import sys
from pathlib import Path

# Add src/ to sys.path
src_path = Path(__file__).resolve().parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from script.cli import main

if __name__ == "__main__":
    main()
