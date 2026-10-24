"""Métricas de calidad: LOC, complejidad y mantenibilidad (SEI aproximada)."""

from __future__ import annotations

import ast
import math

_DECISION_NODES = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.IfExp,
    ast.ExceptHandler,
    ast.With,
    ast.AsyncWith,
    ast.Assert,
    ast.Match,
    ast.BoolOp,
)


def count_loc(source: str) -> tuple[int, int]:
    """Devuelve (líneas totales no vacías, líneas de código sin comentarios)."""
    total = 0
    code = 0
    for line in source.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        total += 1
        if not stripped.startswith("#"):
            code += 1
    return total, code


def cyclomatic(node: ast.AST) -> int:
    return 1 + sum(1 for child in ast.walk(node) if isinstance(child, _DECISION_NODES))


def halstead_volume(tree: ast.AST) -> float:
    """Aproximación de Halstead: operadores = tipos de nodo, operandos = nombres."""
    operators: set[str] = set()
    operands: set[str] = set()
    n_operators = 0
    n_operands = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.Name, ast.Constant, ast.Attribute)):
            n_operands += 1
            operands.add(type(node).__name__)
        elif isinstance(node, ast.AST) and type(node) not in (ast.Module, ast.Expr, ast.Load):
            n_operators += 1
            operators.add(type(node).__name__)
    vocabulary = len(operators) + len(operands)
    length = n_operators + n_operands
    if vocabulary <= 1 or length <= 0:
        return 0.0
    return length * math.log2(vocabulary)


def maintainability_index(volume: float, complexity: float, loc: int) -> float:
    """Índice de mantenibilidad SEI normalizado a 0-100."""
    if loc <= 0:
        return 100.0
    raw = 171 - 5.2 * math.log(max(volume, 1.0)) - 0.23 * complexity - 16.2 * math.log(loc)
    return max(0.0, min(100.0, raw * 100.0 / 171.0))
