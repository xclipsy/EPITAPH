"""Tipos compartidos por los analizadores."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ImportRef:
    module: str
    level: int = 0
    names: list[str] = field(default_factory=list)
    raw: str = ""


@dataclass
class FunctionInfo:
    name: str
    lineno: int
    end_lineno: int
    cyclomatic: int = 1
    has_doc: bool = False
    is_private: bool = False


@dataclass
class ModuleInfo:
    path: str
    lang: str
    loc: int = 0
    sloc: int = 0
    classes: list[str] = field(default_factory=list)
    functions: list[FunctionInfo] = field(default_factory=list)
    imports: list[ImportRef] = field(default_factory=list)
    has_main_guard: bool = False
    docstring: str = ""
    is_package_init: bool = False
    syntax_error: str | None = None
    hash: str = ""
    cyclomatic_avg: float = 0.0
    maintainability: float = 0.0
    halstead_volume: float = 0.0
