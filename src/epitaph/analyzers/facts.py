"""Orquestador del análisis determinista."""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

from . import languages
from .ast_generic import parse_generic
from .ast_python import parse_python
from .dead_code import find_orphans
from .dependency_graph import build_graph, find_cycles, internal_names
from .entrypoints import detect_entrypoints
from .scanner import Scanner
from .secrets import scan_text
from .types import ModuleInfo

SCHEMA_VERSION = 1


def analyze(root: Path, include_secrets: bool = True) -> dict:
    root = Path(root).resolve()
    scanner = Scanner(root)

    modules: list[ModuleInfo] = []
    tree: dict = {"name": root.name, "type": "dir", "children": {}}
    secret_findings: list[dict] = []
    scanned_for_secrets = 0

    for path in scanner.iter_files():
        rel = scanner.rel(path)
        _insert_tree(tree, rel)
        lang = languages.language_of(path)
        if lang is None:
            continue
        if lang == "python":
            module = parse_python(path, rel)
        elif lang in languages.CODE_LANGUAGES:
            module = parse_generic(path, rel, lang)
        else:
            continue
        modules.append(module)

        if include_secrets and lang in languages.CODE_LANGUAGES and scanned_for_secrets < 300:
            scanned_for_secrets += 1
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for finding in scan_text(text):
                secret_findings.append({"file": rel, **finding})

    graph = build_graph(modules)
    entrypoints = detect_entrypoints(root, modules)
    cycles = find_cycles(graph)
    orphans = find_orphans(modules, graph, entrypoints)

    total_loc = sum(module.loc for module in modules)
    total_functions = sum(len(module.functions) for module in modules)
    total_classes = sum(len(module.classes) for module in modules)
    maintainability = (
        sum(module.maintainability for module in modules) / len(modules) if modules else 100.0
    )
    complexity = (
        sum(module.cyclomatic_avg for module in modules) / len(modules) if modules else 0.0
    )

    internal = internal_names(modules)
    external = sorted(
        {
            _top_level(ref.module)
            for module in modules
            if module.lang == "python"
            for ref in module.imports
            if ref.module and ref.level == 0 and _top_level(ref.module) not in internal
        }
        - set(sys.stdlib_module_names)
        - {"__future__"}
    )

    js_external = sorted(
        {
            ref.module.split("/")[0]
            for module in modules
            if module.lang in ("javascript", "typescript")
            for ref in module.imports
            if not ref.module.startswith(".")
        }
        - {"node"}
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "root": str(root),
        "name": root.name,
        "languages": languages.summarize(modules),
        "tree": tree,
        "entrypoints": entrypoints,
        "modules": [_module_payload(module) for module in modules],
        "edges": {source: sorted(targets) for source, targets in sorted(graph.items())},
        "cycles": cycles,
        "orphans": orphans,
        "dependencies": {
            "python_imports": external,
            "js_imports": js_external,
        },
        "commands": detect_commands(root, entrypoints),
        "secrets": secret_findings,
        "totals": {
            "files": len(modules),
            "loc": total_loc,
            "functions": total_functions,
            "classes": total_classes,
            "avg_maintainability": round(maintainability, 1),
            "avg_cyclomatic": round(complexity, 2),
        },
        "scanner_truncated": scanner.truncated,
    }


def _module_payload(module: ModuleInfo) -> dict:
    return {
        "path": module.path,
        "lang": module.lang,
        "loc": module.loc,
        "sloc": module.sloc,
        "classes": module.classes,
        "functions": [fn.name for fn in module.functions],
        "function_count": len(module.functions),
        "imports": [
            {"module": ref.module, "level": ref.level, "names": ref.names}
            for ref in module.imports
        ],
        "has_main_guard": module.has_main_guard,
        "docstring": module.docstring[:400],
        "is_package_init": module.is_package_init,
        "syntax_error": module.syntax_error,
        "hash": module.hash,
        "cyclomatic_avg": round(module.cyclomatic_avg, 2),
        "maintainability": round(module.maintainability, 1),
    }


def _top_level(module: str) -> str:
    return module.split(".")[0]


def _insert_tree(tree: dict, rel: str) -> None:
    node = tree
    parts = rel.split("/")
    for part in parts[:-1]:
        node = node["children"].setdefault(part, {"name": part, "type": "dir", "children": {}})
    node["children"].setdefault(parts[-1], {"name": parts[-1], "type": "file", "children": {}})


def detect_commands(root: Path, entrypoints: list[dict]) -> dict:
    install: list[str] = []
    run: list[str] = []
    test: list[str] = []
    lint: list[str] = []

    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        install.append("uv sync" if (root / "uv.lock").exists() else "pip install -e .")
        test.append("pytest")
    if (root / "requirements.txt").exists():
        install.append("pip install -r requirements.txt")
    if (root / "package.json").exists():
        install.append("npm install")
        test.append("npm test")
    if (root / "go.mod").exists():
        install.append("go mod download")
        test.append("go test ./...")
    if (root / "Cargo.toml").exists():
        install.append("cargo build")
        test.append("cargo test")

    for entry in entrypoints:
        command = entry.get("command")
        if command and entry.get("kind") == "console_script":
            run.append(command.split(" = ")[0].strip())
        elif command and entry.get("kind") == "npm_script":
            run.append(command)

    if (root / "pyproject.toml").exists() and not run:
        packages = [path.parent.name for path in root.glob("*/__main__.py")]
        for package in packages:
            run.append(f"python -m {package}")
    if not run:
        for candidate in ("main.py", "app.py", "manage.py"):
            if (root / candidate).exists():
                run.append(f"python {candidate}")

    if (root / "pyproject.toml").exists():
        try:
            content = (root / "pyproject.toml").read_text(encoding="utf-8")
            if "[tool.ruff" in content:
                lint.append("ruff check .")
            if "[tool.black" in content:
                lint.append("black --check .")
        except OSError:
            pass
    if (root / ".eslintrc" ).exists() or (root / "eslint.config.js").exists():
        lint.append("npx eslint .")

    return {
        "install": list(dict.fromkeys(install)),
        "run": list(dict.fromkeys(run)),
        "test": list(dict.fromkeys(test)),
        "lint": list(dict.fromkeys(lint)),
    }


def summarize_dependencies(facts: dict) -> dict:
    counts = Counter()
    for module in facts.get("modules", []):
        for ref in module.get("imports", []):
            if ref.get("level") == 0 and ref.get("module"):
                counts[ref["module"].split(".")[0]] += 1
    return dict(counts)


def to_json(facts: dict) -> str:
    return json.dumps(facts, ensure_ascii=False, indent=2)
