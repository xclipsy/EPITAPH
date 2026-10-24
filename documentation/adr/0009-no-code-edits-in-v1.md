# ADR-009 — Modificación de código fuera de v1

## Contexto

El objetivo de v1 es documentación fiable. Permitir que el modelo edite código
multiplica el riesgo: cambios semánticos, tests roto, dependencias nuevas.

## Decisión

v1 no modifica código. La capacidad queda para v2 detrás de
`--allow-code-edits`, con árbol limpio obligatorio, diff obligatorio, backup,
`undo` y confirmación interactiva. Nunca será el comportamiento por defecto.

## Consecuencias

- La superficie de daño de v1 se limita a README y artefactos derivados.
- Las sugerencias de refactor son propuestas, no parches automáticos.
- El diseño de permisos ya reserva `write:code = deny`.
