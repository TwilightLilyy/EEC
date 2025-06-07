"""Utilities to analyze a Python project for dead code and duplication."""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple


@dataclass
class Definition:
    name: str
    file: Path
    line: int


class DefinitionCollector(ast.NodeVisitor):
    """Collect top-level function, class and variable definitions."""

    def __init__(self) -> None:
        self.definitions: List[Tuple[str, int]] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.definitions.append((node.name, node.lineno))
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.definitions.append((node.name, node.lineno))
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.definitions.append((node.name, node.lineno))
        self.generic_visit(node)


class UsageCollector(ast.NodeVisitor):
    """Collect used names and attributes."""

    def __init__(self) -> None:
        self.names: Set[str] = set()

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load):
            self.names.add(node.id)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        self.names.add(node.attr)
        self.generic_visit(node)


def run_tool(cmd: List[str]) -> Tuple[int, List[str]]:
    """Run an external command and capture its output."""
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False)
    except FileNotFoundError:
        return 0, []
    output = proc.stdout.splitlines()
    return proc.returncode, output


def analyze_project(project_root: str) -> Dict[str, Any]:
    """Analyze the given project directory and return a report."""
    root = Path(project_root)
    definitions: Dict[str, Tuple[Path, int]] = {}
    usages: Set[str] = set()
    duplicate_blocks: Dict[str, List[Dict[str, Any]]] = {}
    stale_todos: List[Dict[str, Any]] = []

    cutoff = time.time() - 30 * 86400

    for file in root.rglob("*.py"):
        try:
            content = file.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        try:
            tree = ast.parse(content)
        except SyntaxError as err:
            print(f"Syntax error in {file}: {err}", file=sys.stderr)
            continue

        module_name = file.relative_to(root).with_suffix("").as_posix().replace("/", ".")

        # definitions
        collector = DefinitionCollector()
        collector.visit(tree)
        for name, line in collector.definitions:
            definitions[f"{module_name}.{name}"] = (file, line)

        for node in tree.body:
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for t in targets:
                    if isinstance(t, ast.Name):
                        definitions[f"{module_name}.{t.id}"] = (file, t.lineno)

        # usages
        usage_collector = UsageCollector()
        usage_collector.visit(tree)
        usages.update(usage_collector.names)

        # duplicate blocks
        lines = [ln.rstrip() for ln in content.splitlines()]
        for i in range(len(lines) - 5):
            block = "\n".join(lines[i : i + 6])
            h = hashlib.sha1(block.encode()).hexdigest()
            entry = {"file": str(file.relative_to(root)), "line": i + 1}
            duplicate_blocks.setdefault(h, []).append(entry)

        # stale TODOs
        if file.stat().st_mtime < cutoff:
            for idx, text in enumerate(lines, 1):
                if "TODO" in text or "FIXME" in text:
                    stale_todos.append({"file": str(file.relative_to(root)), "line": idx})

    dead_code = []
    for full_name, (file, line_no) in definitions.items():
        name = full_name.split(".")[-1]
        if name not in usages:
            dead_code.append({"symbol": full_name, "file": str(file.relative_to(root)), "line": line_no})

    duplicates = [
        {"hash": h, "occurrences": occ}
        for h, occ in duplicate_blocks.items()
        if len(occ) > 1
    ]

    # linting
    flake8_rc, flake8_out = run_tool(["flake8", str(root)])
    mypy_rc, mypy_out = run_tool(["mypy", str(root)])
    lint_messages = flake8_out + mypy_out

    report = {
        "dead_code": dead_code,
        "duplicates": duplicates,
        "stale_todos": stale_todos,
        "lint": {
            "flake8": len(flake8_out) if flake8_rc else 0,
            "mypy": len(mypy_out) if mypy_rc else 0,
            "messages": lint_messages,
        },
    }
    return report


def generate_summary(report: Dict[str, Any], summary_path: Path) -> None:
    """Write a human-readable summary markdown."""
    dead = report["dead_code"]
    dup = report["duplicates"]
    todos = report["stale_todos"]
    lint = report["lint"]
    with summary_path.open("w", encoding="utf-8") as fh:
        fh.write("### Key Findings\n")
        fh.write(f"* {len(dead)} unused symbols detected.\n")
        fh.write(f"* {len(dup)} duplicate code blocks.\n")
        fh.write(f"* {len(todos)} stale TODO/FIXME comments.\n")
        fh.write(
            f"* flake8 errors: {lint['flake8']}, mypy errors: {lint['mypy']}.\n"
        )
        fh.write("#### Suggested Improvements\n")
        fh.write("1. Remove unused code and related tests.\n")
        fh.write("2. Extract duplicate blocks into shared helpers or modules.\n")


def main(argv: List[str]) -> int:
    if len(argv) != 2:
        print("Usage: codebase_cleaner.py <project_root>")
        return 1

    project_root = argv[1]
    report = analyze_project(project_root)

    root = Path(project_root)
    (root / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    generate_summary(report, root / "SUMMARY.md")

    exit_code = 1 if report["dead_code"] or report["duplicates"] else 0
    return exit_code


if __name__ == "__main__":
    sys.exit(main(sys.argv))
