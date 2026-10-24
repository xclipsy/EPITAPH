"""Parser AST para Python."""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path

from .metrics import count_loc, cyclomatic, halstead_volume, maintainability_index
from .types import FunctionInfo, ImportRef, ModuleInfo


def _module_name(path: Path) -> str:
    return path.stem


def _docstring(node: ast.AST) -> str:
    try:
        return ast.get_docstring(node) or ""
    except TypeError:
        return ""


def parse_python(path: Path, rel: str) -> ModuleInfo:
    info = ModuleInfo(path=rel, lang="python")
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        info.syntax_error = str(exc)
        return info

    info.hash = hashlib.sha256(source.encode("utf-8", errors="replace")).hexdigest()
    info.loc, info.sloc = count_loc(source)
    info.is_package_init = path.name == "__init__.py"

    try:
        tree = ast.parse(source, filename=rel)
    except SyntaxError as exc:
        info.syntax_error = f"{exc.msg} (línea {exc.lineno})"
        return info

    info.docstring = _docstring(tree)

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            info.classes.append(node.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            info.functions.append(
                FunctionInfo(
                    name=node.name,
                    lineno=node.lineno,
                    end_lineno=getattr(node, "end_lineno", node.lineno),
                    cyclomatic=cyclomatic(node),
                    has_doc=bool(_docstring(node)),
                    is_private=node.name.startswith("_"),
                )
            )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                info.imports.append(
                    ImportRef(module=alias.name, names=[alias.name], raw=f"import {alias.name}")
                )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            info.imports.append(
                ImportRef(
                    module=module,
                    level=node.level,
                    names=[alias.name for alias in node.names],
                    raw=f"from {'.' * node.level}{module} import ...",
                )
            )
        elif isinstance(node, ast.If):
            if _is_main_guard(node):
                info.has_main_guard = True

    if info.functions:
        info.cyclomatic_avg = sum(fn.cyclomatic for fn in info.functions) / len(info.functions)
    info.halstead_volume = halstead_volume(tree)
    info.maintainability = maintainability_index(
        info.halstead_volume,
        sum(fn.cyclomatic for fn in info.functions) or 1,
        max(info.sloc, 1),
    )
    return info


def _is_main_guard(node: ast.If) -> bool:
    test = node.test
    if not isinstance(test, ast.Compare) or len(test.comparators) != 1:
        return False
    left = test.left
    right = test.comparators[0]
    return (
        isinstance(left, ast.Name)
        and left.id == "__name__"
        and isinstance(right, ast.Constant)
        and right.value == "__main__"
    )


def module_name(rel: str) -> str:
    return _module_name(Path(rel))
