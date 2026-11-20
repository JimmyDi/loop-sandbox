"""Validate built archives and import the installed wheel outside this checkout."""

import configparser
import os
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import zipfile
from email.parser import Parser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def verify():
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    wheel = ROOT / "dist" / f"loop_sandbox-{version}-py3-none-any.whl"
    source = ROOT / "dist" / f"loop_sandbox-{version}.tar.gz"
    license_text = (ROOT / "LICENSE").read_text()
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        assert any(n.endswith("/licenses/LICENSE") for n in names), "Wheel license missing"
        license_path = next(n for n in names if n.endswith("/licenses/LICENSE"))
        assert archive.read(license_path).decode() == license_text
        metadata_path = next(n for n in names if n.endswith(".dist-info/METADATA"))
        metadata = Parser().parsestr(archive.read(metadata_path).decode())
        assert metadata["Name"] == "loop-sandbox" and metadata["Version"] == version
        assert metadata["License-Expression"] == "MIT"
        assert metadata["License-File"] == "LICENSE"
        assert metadata["Description-Content-Type"] == "text/markdown"
        assert "# Loop Sandbox" in metadata.get_payload()
        entries = configparser.ConfigParser()
        entries.read_string(
            archive.read(metadata_path.replace("METADATA", "entry_points.txt")).decode()
        )
        assert entries["console_scripts"]["loop-sandbox"] == "loop_sandbox.server.cli:main"
        assert all(
            n.startswith(("loop_sandbox/", f"loop_sandbox-{version}.dist-info/")) for n in names
        )
        assert not any("__pycache__" in n or n.endswith(".pyc") for n in names)
    with tarfile.open(source) as archive:
        members = archive.getnames()
        assert (
            archive.extractfile(f"loop_sandbox-{version}/LICENSE").read().decode() == license_text
        )
        assert not any(
            any(
                part in {".env", ".loop-sandbox", ".git", ".venv", "artifacts", "dist"}
                for part in Path(n).parts
            )
            for n in members
        ), "Private/runtime files in source archive"
    with tempfile.TemporaryDirectory(prefix="loop-sandbox-package-") as directory:
        target = Path(directory) / "installed"
        subprocess.run(
            [
                "uv",
                "pip",
                "install",
                "--python",
                sys.executable,
                "--target",
                str(target),
                "--no-deps",
                str(wheel),
            ],
            check=True,
            capture_output=True,
        )
        env = dict(
            os.environ,
            PYTHONPATH=str(target),
            DEMO_API_KEY="package-verification-only",
            WORKER_TOKEN="package-worker-only",
        )
        env.pop("LOOP_SANDBOX_CREDENTIALS", None)
        subprocess.run(
            [
                sys.executable,
                "-c",
                "import loop_sandbox; from pathlib import Path; import sys; assert Path(loop_sandbox.__file__).is_relative_to(Path(sys.argv[1])); import loop_sandbox.server.main; import loop_sandbox.worker.app",
                str(target),
            ],
            cwd=directory,
            env=env,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [sys.executable, "-m", "loop_sandbox.server.cli", "--help"],
            cwd=directory,
            env=env,
            check=True,
            capture_output=True,
        )
    print("PASS: archive boundaries, license, metadata, CLI and installed application imports")


if __name__ == "__main__":
    verify()
