# ADR-011 — Preferencias del usuario desde el chat

## Contexto

Cada proyecto tiene convenciones propias: orden de secciones, tono, vocabulario,
estilo de modularización. Editar TOML a mano es correcto pero poco descubrible.

## Decisión

El chat acepta lenguaje natural y distingue tres intenciones: comando, consulta y
**preferencia**. Una preferencia no se aplica directamente:

1. Se detecta de forma determinista o con el rol `chat`.
2. Se construye una propuesta con un **ámbito cerrado**.
3. Se valida contra un esquema y unos límites.
4. Se muestra el valor propuesto y los conflictos.
5. El usuario confirma.
6. Se persiste en `.epitaph/preferences.toml` y se audita.

Una preferencia **no puede ampliar permisos**, desactivar el enmascarado de
secretos ni silenciar categorías `security`. Tampoco cambia el modelo o el
backend: eso requiere `/model` o `/config`.

## Consecuencias

- La personalización es explícita, reversible (`/prefs rm`) y auditable.
- `config.toml` explícito gana sobre `preferences.toml`.
- El prompt recibe las directivas como restricciones, con presupuesto de tokens.
- Las preferencias filtran sugerencias mostrando cuántas se ocultaron.
