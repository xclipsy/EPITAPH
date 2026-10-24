# ADR-005 — Roles de modelo separados

## Contexto

Resumir un módulo, redactar el README, priorizar sugerencias y conversar tienen
costes y requisitos distintos. Un único modelo grande para todo es lento en CPU;
uno pequeño para todo degrada la prosa.

## Decisión

Cuatro roles: `summarizer`, `writer`, `advisor` y `chat`. Cada rol puede apuntar a
un modelo distinto. La selección se basa en metadatos reales del modelo
(`parameter_size`, cuantización, tamaño en disco) y en la RAM disponible, no en
nombres hardcodeados. Si el modelo preferido no está instalado, hay fallback
explícito y visible.

## Consecuencias

- Un equipo modesto puede usar 1.5b para resumir y 3b para redactar.
- La configuración es legible y versionable (`[llm.roles]`).
- El usuario puede fijar roles con `epitaph models role <rol> <modelo>`.
