"""Bootstrap local private credentials using the package CLI."""

import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "src"))

from loop_sandbox.server.cli import configure  # noqa: E402

configure(root)
print("Local configuration ready; credentials preserved and hidden.")
