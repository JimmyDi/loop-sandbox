"""Check local import cycles and component dependency boundaries without imports."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src"
PACKAGE = SOURCE / "loop_sandbox"
ALLOWED = {
    "contracts": {"contracts"},
    "runtime": {"runtime"},
    "worker": {"worker", "contracts"},
    "server": {"server", "runtime", "contracts"},
    "integrations": {"integrations", "server", "contracts"},
}


def check():
    modules = {}
    for path in PACKAGE.rglob("*.py"):
        parts = path.relative_to(SOURCE).with_suffix("").parts
        name = ".".join(parts[:-1] if parts[-1] == "__init__" else parts)
        modules[name] = path
    graph = {name: set() for name in modules}
    errors = []
    for name, path in modules.items():
        for node in ast.walk(ast.parse(path.read_text())):
            targets = []
            if isinstance(node, ast.Import):
                targets = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    errors.append(f"{path.relative_to(ROOT)}: use absolute package imports")
                    continue
                base = node.module or ""
                targets = [base, *(base + "." + alias.name for alias in node.names)]
            for target in targets:
                if not target.startswith("loop_sandbox."):
                    continue
                origin = name.split(".")[1]
                destination = target.split(".")[1]
                # The application entry point is the composition root.
                if name != "loop_sandbox.server.main" and destination not in ALLOWED[origin]:
                    errors.append(f"{name} must not import {target}")
                if target in modules and target != name:
                    graph[name].add(target)

    visiting, visited = set(), set()

    def visit(name, chain):
        if name in visiting:
            errors.append("Import cycle: " + " -> ".join([*chain, name]))
            return
        if name in visited:
            return
        visiting.add(name)
        for target in sorted(graph[name]):
            visit(target, [*chain, name])
        visiting.remove(name)
        visited.add(name)

    for name in sorted(graph):
        visit(name, [])
    if errors:
        raise SystemExit("\n".join(sorted(set(errors))))
    print(f"PASS: {len(modules)} modules, no import cycles or component boundary violations")


if __name__ == "__main__":
    check()
