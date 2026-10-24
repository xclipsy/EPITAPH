"""Extracción de imports y declaraciones para lenguajes sin AST nativo (regex acotada)."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from .metrics import count_loc
from .types import FunctionInfo, ImportRef, ModuleInfo

JS_IMPORT = re.compile(r"""import\s+(?:[^'"]*?\s+from\s+)?['"]([^'"]+)['"]""")
JS_REQUIRE = re.compile(r"""require\(\s*['"]([^'"]+)['"]\s*\)""")
GO_IMPORT = re.compile(r"""^\s*(?:import\s+)?["']([^"']+)["']\s*$""", re.MULTILINE)
JAVA_IMPORT = re.compile(r"""^\s*import\s+(?:static\s+)?([\w.]+)\s*;""", re.MULTILINE)
RUST_USE = re.compile(r"""^\s*use\s+([\w:]+)""", re.MULTILINE)
PHP_USE = re.compile(r"""^\s*use\s+([\w\\]+)""", re.MULTILINE)

_MODIFIERS = r"(?:public|private|protected|internal|static|final|abstract|sealed|open|data|synchronized|native|default|async|export|partial)"

DECLARATIONS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "javascript": (
        (rf"^\s*{_MODIFIERS}*\s*(?:class|interface)\s+([A-Za-z_$][\w$]*)",),
        (
            rf"^\s*{_MODIFIERS}*\s*function\s*\*?\s*([A-Za-z_$][\w$]*)",
            r"^\s*(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\(",
        ),
    ),
    "typescript": (
        (
            rf"^\s*{_MODIFIERS}*\s*(?:class|interface|enum|type)\s+([A-Za-z_$][\w$]*)",
        ),
        (
            rf"^\s*{_MODIFIERS}*\s*function\s*\*?\s*([A-Za-z_$][\w$]*)",
            r"^\s*(?:export\s+)?(?:const|let)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\(",
        ),
    ),
    "go": (
        (r"^type\s+([A-Za-z_]\w*)\s+(?:struct|interface)",),
        (r"^func\s+(?:\([^)]*\)\s*)?([A-Za-z_]\w*)",),
    ),
    "java": (
        (rf"^\s*{_MODIFIERS}*\s*(?:class|interface|enum|record|@interface)\s+([A-Za-z_]\w*)",),
        (
            r"^\s*(?:(?:public|private|protected|static|final|abstract|synchronized|native|default)\s+)"
            r"[^;{}=()\n]*?\b([A-Za-z_]\w*)\s*\([^;{)]*\)\s*(?:throws\s+[\w.,\s]+)?\{",
        ),
    ),
    "kotlin": (
        (rf"^\s*{_MODIFIERS}*\s*(?:class|interface|object)\s+([A-Za-z_]\w*)",),
        (r"^\s*(?:@\w+\s+)*(?:(?:public|private|protected|internal|suspend|inline|override)\s+)*fun\s+(?:<[^>]*>\s*)?([A-Za-z_]\w*)",),
    ),
    "rust": (
        (r"^\s*(?:pub\s+)?(?:struct|enum|trait|union)\s+([A-Za-z_]\w*)",),
        (r"^\s*(?:pub\s+(?:\([^)]*\)\s*)?)?(?:async\s+)?(?:unsafe\s+)?fn\s+([A-Za-z_]\w*)",),
    ),
    "php": (
        (rf"^\s*{_MODIFIERS}*\s*(?:class|interface|trait|enum)\s+([A-Za-z_]\w*)",),
        (rf"^\s*{_MODIFIERS}*\s*function\s+&?\s*([A-Za-z_]\w*)",),
    ),
    "ruby": (
        (r"^\s*(?:class|module)\s+([A-Z]\w*)",),
        (r"^\s*def\s+(?:self\.)?([A-Za-z_]\w*[?!=]?)",),
    ),
    "csharp": (
        (r"^\s*(?:(?:public|private|protected|internal|static|sealed|abstract|partial)\s+)*"
         r"(?:class|interface|struct|enum|record)\s+([A-Za-z_]\w*)",),
        (r"^\s*(?:(?:public|private|protected|internal|static|virtual|override|async|sealed)\s+)+"
         r"[^;{}=()\n]*?\b([A-Za-z_]\w*)\s*\([^;{)]*\)\s*\{",),
    ),
    "c": ((r"^typedef\s+(?:struct|enum)\s+([A-Za-z_]\w*)",), ()),
    "cpp": (
        (r"^\s*(?:class|struct)\s+([A-Za-z_]\w*)",),
        (),
    ),
    "shell": ((), (r"^\s*(?:function\s+)?([A-Za-z_]\w*)\s*\(\)\s*\{",)),
}

_COMPILED = {
    lang: (
        tuple(re.compile(pattern, re.MULTILINE) for pattern in classes),
        tuple(re.compile(pattern, re.MULTILINE) for pattern in functions),
    )
    for lang, (classes, functions) in DECLARATIONS.items()
}


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

    _extract_declarations(info, source, lang)

    info.maintainability = 100.0 if info.sloc < 200 else 70.0
    return info


def _extract_declarations(info: ModuleInfo, source: str, lang: str) -> None:
    """Cuenta clases y funciones con patrones acotados (nunca lanza)."""
    patterns = _COMPILED.get(lang)
    if patterns is None:
        return
    class_patterns, function_patterns = patterns

    for pattern in class_patterns:
        for match in pattern.finditer(source):
            name = match.group(1)
            if name and name not in info.classes:
                info.classes.append(name)

    for pattern in function_patterns:
        for match in pattern.finditer(source):
            name = match.group(1)
            if not name or any(fn.name == name for fn in info.functions):
                continue
            lineno = source.count("\n", 0, match.start()) + 1
            info.functions.append(
                FunctionInfo(
                    name=name,
                    lineno=lineno,
                    end_lineno=lineno,
                    is_private=name.startswith("_"),
                )
            )

    if info.functions:
        info.cyclomatic_avg = 1.0
