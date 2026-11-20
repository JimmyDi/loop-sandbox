"""Local credential bootstrap; secrets are never printed."""

import argparse
import fcntl
import hashlib
import os
from pathlib import Path

from loop_sandbox.server.credentials import new_credentials, read_credentials, save_credentials


def configure(root: Path, rotate: bool = False):
    directory = root / ".loop-sandbox"
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if directory.is_symlink():
        raise ValueError("Refusing a symlink configuration directory")
    directory.chmod(0o700)
    env = root / ".env"
    if env.is_symlink():
        raise ValueError("Refusing a symlink environment file")
    if env.exists():
        env.chmod(0o600)
    descriptor = os.open(directory / "setup.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        target = directory / "credentials.json"
        if target.is_symlink():
            raise ValueError("Refusing a symlink credential file")
        if target.exists():
            value = read_credentials(target)
            if rotate:
                save_credentials(target, new_credentials(value["client_id"]))
        elif rotate:
            raise ValueError("Run loop-sandbox init before rotating credentials")
        else:
            value = new_credentials()
            env = root / ".env"
            if env.exists():
                for line in env.read_text().splitlines():
                    if line.startswith("DEMO_API_KEY="):
                        old = line.split("=", 1)[1].strip().strip("\"'")
                        if old and old != "replace-with-a-random-local-key":
                            value = {
                                "token": old,
                                "client_id": hashlib.sha256(("Bearer " + old).encode()).hexdigest(),
                            }
                env.chmod(0o600)
            save_credentials(target, value)
        env = root / ".env"
        if not env.exists():
            template = root / ".env.example"
            content = template.read_text() if template.exists() else ""
            content = "\n".join(
                line for line in content.splitlines() if not line.startswith("DEMO_API_KEY=")
            )
            fd = os.open(env, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "w") as stream:
                stream.write(content + "\n")
    return target


def main():
    parser = argparse.ArgumentParser(prog="loop-sandbox")
    parser.add_argument("command", choices=["init", "rotate-token"])
    parser.add_argument("--directory", type=Path, default=Path.cwd())
    args = parser.parse_args()
    try:
        configure(args.directory, args.command == "rotate-token")
    except (OSError, ValueError):
        parser.exit(
            1, "Credential setup failed; check private configuration files and permissions.\n"
        )
    print("Credentials ready in .loop-sandbox/credentials.json (secret hidden).")


if __name__ == "__main__":
    main()
