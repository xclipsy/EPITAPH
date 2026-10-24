# ADR-007 — Escritura atómica con backup y auditoría

## Contexto

Una escritura interrumpida o un bug del merge no debe dejar el README corrupto ni
sin posibilidad de volver atrás.

## Decisión

Antes de escribir:

1. Se comprueba el permiso `write:readme`.
2. Se exige árbol de git limpio (salvo `--force`).
3. Se copia el original a `.epitaph/backups/` con retención configurable.
4. Se escribe en un temporal y se renombra (`os.replace`).
5. Se registra el evento en `.epitaph/audit.log` (append-only).

`epitaph undo` restaura el backup más reciente.

## Consecuencias

- La escritura es atómica a nivel de sistema de archivos.
- Toda modificación es reversible y auditable.
- El coste en disco es acotado por la retención.
