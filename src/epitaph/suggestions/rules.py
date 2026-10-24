"""Reglas deterministas de sugerencias."""

from __future__ import annotations

import hashlib
from pathlib import Path

CATEGORY_WEIGHT = {
    "security": 100,
    "architecture": 40,
    "dependencies": 35,
    "modularity": 30,
    "dead-code": 20,
    "tooling": 15,
    "documentation": 10,
}

SEVERITY_WEIGHT = {"critical": 40, "high": 30, "medium": 20, "low": 10}


def _item(rule: str, category: str, severity: str, title: str, evidence: str, action: str) -> dict:
    key = hashlib.sha1(f"{category}|{rule}|{evidence}".encode()).hexdigest()[:10]
    return {
        "key": key,
        "rule": rule,
        "category": category,
        "severity": severity,
        "title": title,
        "evidence": evidence,
        "action": action,
        "evidence_hash": hashlib.sha1(evidence.encode()).hexdigest()[:12],
    }


def build(facts: dict, deps: dict | None = None, root: Path | None = None) -> list[dict]:
    items: list[dict] = []

    for cycle in facts.get("cycles", [])[:5]:
        items.append(
            _item(
                "dependency-cycle",
                "architecture",
                "high",
                f"Ciclo de dependencias: {' → '.join(cycle[:4])}",
                " | ".join(cycle),
                "Extrae la parte compartida a un módulo neutral o invierte la dependencia.",
            )
        )

    for orphan in facts.get("orphans", [])[:8]:
        items.append(
            _item(
                "orphan-module",
                "dead-code",
                "medium",
                f"Módulo sin importadores: {orphan}",
                orphan,
                "Confirma si sigue en uso; si no, elimínalo o documéntalo como entrypoint.",
            )
        )

    for finding in facts.get("secrets", [])[:5]:
        items.append(
            _item(
                "secret-detected",
                "security",
                "critical",
                f"Posible secreto en {finding['file']}",
                f"{finding['file']}:{finding['type']}",
                "Rota la credencial, elimínala del historial y usa variables de entorno.",
            )
        )

    for module in facts.get("modules", []):
        if module.get("loc", 0) > 400:
            items.append(
                _item(
                    "large-module",
                    "modularity",
                    "medium",
                    f"Módulo grande: {module['path']} ({module['loc']} líneas)",
                    module["path"],
                    "Divide por responsabilidad y deja el módulo por debajo de ~300 líneas.",
                )
            )
        if module.get("maintainability", 100) < 40:
            items.append(
                _item(
                    "low-maintainability",
                    "modularity",
                    "high",
                    f"Mantenibilidad baja en {module['path']}",
                    f"{module['path']}:{module['maintainability']}",
                    "Reduce complejidad y extrae funciones con responsabilidades claras.",
                )
            )
        if module.get("syntax_error"):
            items.append(
                _item(
                    "syntax-error",
                    "architecture",
                    "high",
                    f"Error de sintaxis en {module['path']}",
                    f"{module['path']}:{module['syntax_error']}",
                    "Corrige el error antes de confiar en el análisis.",
                )
            )

    if deps:
        for missing in deps.get("missing", [])[:10]:
            items.append(
                _item(
                    "missing-dependency",
                    "dependencies",
                    "high",
                    f"Dependencia no declarada: {missing['package']}",
                    missing["package"],
                    f"Añade `{missing['package']}` a requirements.txt tras confirmar la versión.",
                )
            )
        for unused in deps.get("unused", [])[:5]:
            items.append(
                _item(
                    "unused-dependency",
                    "dependencies",
                    "low",
                    f"Dependencia declarada sin uso: {unused}",
                    unused,
                    "Verifica el uso dinámico antes de eliminarla.",
                )
            )

    if root is not None:
        if not (root / "tests").exists() and not (root / "test").exists():
            items.append(
                _item(
                    "no-tests",
                    "tooling",
                    "medium",
                    "No se detecta carpeta de pruebas",
                    "tests/",
                    "Añade una suite mínima y un comando de test reproducible.",
                )
            )
        if not any((root / name).exists() for name in ("LICENSE", "LICENSE.md", "COPYING")):
            items.append(
                _item(
                    "no-license",
                    "documentation",
                    "low",
                    "No se detecta licencia",
                    "LICENSE",
                    "Añade un archivo de licencia para aclarar el uso permitido.",
                )
            )
        if not (root / ".github" / "workflows").exists():
            items.append(
                _item(
                    "no-ci",
                    "tooling",
                    "medium",
                    "No se detecta integración continua",
                    ".github/workflows",
                    "Añade un workflow mínimo de lint y tests.",
                )
            )

    return items


def score(item: dict) -> int:
    return (
        CATEGORY_WEIGHT.get(item.get("category", ""), 0)
        + SEVERITY_WEIGHT.get(item.get("severity", "low"), 0)
    )
