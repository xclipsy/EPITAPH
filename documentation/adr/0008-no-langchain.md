# ADR-008 — Paquete independiente, sin `langchain`

## Contexto

PRAXIA usa `langchain`, `langgraph` y `reportlab`. Esas dependencias añaden peso,
tiempo de instalación y superficies de fallo que no aportan al problema de
EPITAPH.

## Decisión

EPITAPH se implementa con `httpx` y la biblioteca estándar para el proveedor,
`pydantic` para el contrato, `rich`/`prompt_toolkit` para la TUI, `pathspec` para
ignores y `watchdog` para el watcher. Los conceptos útiles de PRAXIA (roles,
selector de modelos, resolución local) se portan, no se importan.

## Consecuencias

- Instalación rápida y auditable.
- Menos versiones incompatibles.
- La lógica de orquestación es propia y testeable sin frameworks.
