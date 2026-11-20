"""Export or check HTTP contracts offline, without starting either application."""

import argparse
import json
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail if snapshots are stale")
    args = parser.parse_args()
    # Schema generation never needs real service credentials or a Docker daemon.
    os.environ["DEMO_API_KEY"] = "schema-export-only"
    os.environ["WORKER_TOKEN"] = "schema-export-only"
    from loop_sandbox.server.main import app
    from loop_sandbox.worker.app import app as worker

    root = Path(__file__).resolve().parents[1]
    for name, application in (("sandbox-api", app), ("worker-api", worker)):
        path = root / "specs" / (name + ".json")
        content = json.dumps(application.openapi(), indent=2, sort_keys=True) + "\n"
        if args.check:
            if not path.exists() or path.read_text() != content:
                raise SystemExit(f"Stale contract: {path.name}; run make specs")
        else:
            path.write_text(content)
    print("PASS: HTTP contract snapshots " + ("match" if args.check else "exported"))


if __name__ == "__main__":
    main()
