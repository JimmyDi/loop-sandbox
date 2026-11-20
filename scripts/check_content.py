"""Check source whitespace, English content and local Markdown file links."""

import re
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
DIRECTORIES = ("src", "scripts", "tests", "docs", "specs", "docker", "deploy", ".github")
SUFFIXES = {".py", ".md", ".json", ".toml", ".yaml", ".yml", ".lock"}


def check():
    paths = {
        p
        for p in ROOT.iterdir()
        if p.is_file()
        and (
            p.suffix in SUFFIXES
            or p.name in {"LICENSE", "Makefile", ".gitignore", ".dockerignore", ".gitattributes"}
        )
    }
    for directory in DIRECTORIES:
        paths.update(
            p
            for p in (ROOT / directory).rglob("*")
            if p.is_file() and "__pycache__" not in p.parts and p.suffix in SUFFIXES
        )
    errors = []
    for path in sorted(paths):
        content = path.read_text()
        relative = path.relative_to(ROOT)
        for number, line in enumerate(content.splitlines(), 1):
            if line != line.rstrip():
                errors.append(f"{relative}:{number}: trailing whitespace")
        if re.search(r"[\u4e00-\u9fff]", content):
            errors.append(f"{relative}: repository text must be English")
        if path.suffix == ".md":
            for target in re.findall(r"(?<!!)\[[^\]]*\]\(([^)]+)\)", content):
                target = target.strip().split()[0].strip("<>").split("#", 1)[0]
                if not target or re.match(r"[a-zA-Z][a-zA-Z0-9+.-]*:", target):
                    continue
                if not (path.parent / unquote(target)).exists():
                    errors.append(f"{relative}: missing link {target}")
    if errors:
        raise SystemExit("\n".join(errors))
    print(f"PASS: {len(paths)} source files, whitespace, English content and file links")


if __name__ == "__main__":
    check()
