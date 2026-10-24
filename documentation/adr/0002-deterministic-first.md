# ADR-002 — Determinista primero

## Contexto

Un LLM puede inventar archivos, comandos y versiones. Un README con datos falsos
es peor que no tener README.

## Decisión

Todo lo que se puede calcular se calcula sin modelo: lenguajes, árbol,
dependencias, ciclos, huérfanos, entrypoints, comandos, métricas y licencia. El
LLM solo redacta *overview*, notas de arquitectura y propósito de módulos.

Si el modelo falla, no está disponible o devuelve JSON inválido, se usa la
plantilla determinista. Nunca se bloquea la actualización por culpa del modelo.

## Consecuencias

- El resultado es reproducible y auditable.
- Los tests no necesitan Ollama.
- La calidad de la prosa mejora con el modelo, pero la corrección no depende de
  él.
