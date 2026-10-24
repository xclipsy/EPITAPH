"""Grafo de dependencias internas y detección de ciclos (Tarjan)."""

from __future__ import annotations

import sys
from pathlib import PurePosixPath

from .types import ModuleInfo


def _dotted_candidates(rel: str) -> set[str]:
    """Candidatos de nombre importable para un archivo relativo."""
    path = PurePosixPath(rel)
    parts = list(path.with_suffix("").parts)
    candidates: set[str] = set()
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    if not parts:
        return candidates
    for start in range(len(parts)):
        candidates.add(".".join(parts[start:]))
    return candidates


def build_index(modules: list[ModuleInfo]) -> dict[str, str]:
    index: dict[str, str] = {}
    for module in modules:
        if module.lang != "python":
            continue
        for candidate in _dotted_candidates(module.path):
            index.setdefault(candidate, module.path)
    return index


def _resolve_python(module: ModuleInfo, ref, index: dict[str, str]) -> str | None:
    if ref.level > 0:
        base = PurePosixPath(module.path).parent
        for _ in range(ref.level - 1):
            base = base.parent
        base_parts = [part for part in base.parts if part not in ("", ".")]
        target = ".".join([*base_parts, *(ref.module.split(".") if ref.module else [])])
        for candidate in (target, f"{target}.__init__"):
            if candidate in index:
                return index[candidate]
        return None

    parts = ref.module.split(".") if ref.module else []
    for end in range(len(parts), 0, -1):
        candidate = ".".join(parts[:end])
        if candidate in index:
            return index[candidate]
    return None


_JS_EXTENSIONS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")


def _resolve_js(module: ModuleInfo, ref, known: set[str]) -> str | None:
    target = ref.module
    if not target.startswith("."):
        return None
    base = PurePosixPath(module.path).parent / target
    normalized = _normalize(str(base))
    candidates = [normalized]
    candidates.extend(normalized + ext for ext in _JS_EXTENSIONS)
    candidates.extend(f"{normalized}/index{ext}" for ext in _JS_EXTENSIONS)
    for candidate in candidates:
        if candidate in known:
            return candidate
    return None


def _normalize(path: str) -> str:
    parts: list[str] = []
    for part in path.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            if parts:
                parts.pop()
            continue
        parts.append(part)
    return "/".join(parts)


def internal_names(modules: list[ModuleInfo]) -> set[str]:
    """Nombres de primer nivel que pertenecen al propio repositorio."""
    names: set[str] = set()
    for module in modules:
        if module.lang != "python":
            continue
        for candidate in _dotted_candidates(module.path):
            names.add(candidate.split(".")[0])
    return names


def build_graph(modules: list[ModuleInfo]) -> dict[str, set[str]]:
    index = build_index(modules)
    known = {module.path for module in modules}
    graph: dict[str, set[str]] = {module.path: set() for module in modules}

    for module in modules:
        for ref in module.imports:
            target: str | None = None
            if module.lang == "python":
                target = _resolve_python(module, ref, index)
            elif module.lang in ("javascript", "typescript"):
                target = _resolve_js(module, ref, known)
            elif module.lang in ("go", "java", "kotlin", "rust", "php"):
                tail = ref.module.replace("\\", "/").rstrip("/").split("/")[-1]
                for candidate in known:
                    if PurePosixPath(candidate).stem == tail:
                        target = candidate
                        break
            if target and target != module.path:
                graph[module.path].add(target)
    return graph


def find_cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    """Componentes fuertemente conexas con más de un nodo (Tarjan iterativo)."""
    index = 0
    stack: list[str] = []
    on_stack: set[str] = set()
    indices: dict[str, int] = {}
    low: dict[str, int] = {}
    result: list[list[str]] = []

    old_limit = sys.getrecursionlimit()
    sys.setrecursionlimit(max(old_limit, 10000))
    try:

        def strongconnect(node: str) -> None:
            nonlocal index
            indices[node] = low[node] = index
            index += 1
            stack.append(node)
            on_stack.add(node)

            for neighbour in graph.get(node, ()):
                if neighbour not in indices:
                    strongconnect(neighbour)
                    low[node] = min(low[node], low[neighbour])
                elif neighbour in on_stack:
                    low[node] = min(low[node], indices[neighbour])

            if low[node] == indices[node]:
                component: list[str] = []
                while True:
                    item = stack.pop()
                    on_stack.discard(item)
                    component.append(item)
                    if item == node:
                        break
                if len(component) > 1:
                    result.append(sorted(component))

        for node in graph:
            if node not in indices:
                strongconnect(node)
    finally:
        sys.setrecursionlimit(old_limit)

    return sorted(result, key=lambda cycle: cycle[0])
