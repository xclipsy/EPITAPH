# ADR-003 — Marcadores y merge por fingerprint

## Contexto

Regenerar el README completo destruye el texto escrito por humanos y produce
diffs enormes en cada ejecución.

## Decisión

Las secciones generadas se delimitan con marcadores HTML:

```markdown
<!-- epitaph:begin id=overview fp=9f2a1c3b4d5e -->
...
<!-- epitaph:end id=overview -->
```

El `fp` es el hash del contenido normalizado. En cada run solo se reescribe la
sección cuyo fingerprint cambió. El texto fuera de los marcadores se conserva
byte a byte. Si los marcadores están corruptos, no se escribe el README: se
genera `README.suggested.md`.

## Consecuencias

- Idempotencia verificable: dos runs sin cambios ⇒ cero diff.
- El diff es mínimo y revisable.
- Un README sin marcadores recibe las secciones al final, sin tocar lo existente.
