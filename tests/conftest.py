import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# The dashboard and the keep-alive scripts run as loose scripts, not packages.
sys.path[:0] = [str(ROOT / "dashboard"), str(ROOT / ".github" / "scripts")]
