# ADR-004 — Cadencia configurable con gate semántico

## Contexto

Ejecutar en cada guardado puede generar churn de diffs y consumir CPU. Ejecutar
solo a mano hace que la documentación se quede obsoleta.

## Decisión

El usuario elige la cadencia en el primer arranque: por guardado, cada N minutos,
por inactividad o manual. El watcher solo registra eventos; el trigger decide
cuándo ejecutar aplicando debounce, cooldown y pausa.

Antes de llamar al modelo hay un **gate semántico**: si ningún archivo relevante
cambió, el run termina sin tokens y sin diff.

## Consecuencias

- El coste es proporcional a lo que cambia, no al tamaño del repo.
- La cadencia se puede cambiar en caliente con `/every`.
- Los modos son intercambiables sin tocar el pipeline.
