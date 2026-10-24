"""Extracción de imports para lenguajes sin AST nativo (regex acotada)."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from .metrics import count_loc
from .types import ImportRef, ModuleInfo

JS_IMPORT = re.compile(r"""import\s+(?:[^'"]*?\s+from\s+)?['"]([^'"]+)['"]""")
JS_REQUIRE = re.compile(r"""require\(\s*['"]([^'"]+)['"]\s*\)""")
GO_IMPORT = re.compile(r"""^\s*(?:import\s+)?["']([^"']+)["']\s*$""", re.MULTILINE)
JAVA_IMPORT = re.compile(r"""^\s*import\s+(?:static\s+)?([\w.]+)\s*;""", re.MULTILINE)
RUST_USE = re.compile(r"""^\s*use\s+([\w:]+)""", re.MULTILINE)
PHP_USE = re.compile(r"""^\s*use\s+([\w\\]+)""", re.MULTILINE)


def parse_generic(path: Path, rel: str, lang: str) -> ModuleInfo:
    info = ModuleInfo(path=rel, lang=lang)
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        info.syntax_error = str(exc)
        return info

    info.hash = hashlib.sha256(source.encode("utf-8", errors="replace")).hexdigest()
    info.loc, info.sloc = count_loc(source)

    targets: list[str] = []
    if lang in ("javascript", "typescript"):
        targets.extend(JS_IMPORT.findall(source))
        targets.extend(JS_REQUIRE.findall(source))
    elif lang == "go":
        targets.extend(GO_IMPORT.findall(source))
    elif lang in ("java", "kotlin"):
        targets.extend(JAVA_IMPORT.findall(source))
    elif lang == "rust":
        targets.extend(RUST_USE.findall(source))
    elif lang == "php":
        targets.extend(PHP_USE.findall(source))

    for target in dict.fromkeys(targets):
        info.imports.append(ImportRef(module=target, raw=target))

    info.maintainability = 100.0 if info.sloc < 200 else 70.0
    return info
