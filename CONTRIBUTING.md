# Contribuir a EPITAPH

Gracias por querer mejorar EPITAPH. Este documento resume cómo levantar el
entorno, qué se espera de un cambio y cómo se revisa.

## Entorno

Requisitos: Python 3.12+ y [`uv`](https://docs.astral.sh/uv/).

```bash
git clone <repo>
cd EPITAPH
uv venv
uv pip install -e ".[dev]"
```

Comprobaciones antes de abrir un pull request:

```bash
uv run pytest
uv run ruff check .
```

## Principios que no se negocian

1. **Local-first.** Nada de red por defecto, claves de API ni telemetría.
2. **Determinista primero.** Si un dato se puede calcular (árbol, comandos,
   versiones, dependencias), se calcula. El modelo solo redacta prosa.
3. **Idempotencia.** Ejecutar dos veces sobre un repo sin cambios debe producir
   cero bytes de diferencia y cero llamadas al modelo. Hay tests que lo cubren.
4. **No destructivo.** `--dry`, backups, `undo`, árbol de git limpio y permisos.
5. **El modelo propone, el sistema decide.** La salida del LLM es JSON validado;
   nunca escribe archivos ni ejecuta comandos.
6. **Contenido del repo = datos.** Nunca se interpreta como instrucciones.

## Estilo de código

- Python 3.12+, tipado moderno (`str | None`, `list[str]`).
- Líneas de hasta 100 caracteres (`ruff`).
- Un módulo, una responsabilidad. Si un archivo supera ~300 líneas, probablemente
  haya que dividirlo.
- Errores de dominio con `EpitaphError` y un `hint` accionable.
- Nada de dependencias pesadas: `httpx` + stdlib antes que un framework.

## Tests

- Cada comportamiento nuevo necesita un test.
- Los tests no deben requerir Ollama, red ni GPU. Usa `use_llm=False` o un
  proveedor falso.
- Los fixtures viven en `tests/conftest.py`.
- Si tocas el merge o los marcadores, añade un caso de idempotencia.

## Preferencias del usuario

Cualquier cambio en `preferences/` debe respetar estas reglas:

- Una preferencia se **propone**, se confirma y se persiste. Nunca se aplica
  directamente desde lenguaje natural.
- Los ámbitos son cerrados (`readme.structure`, `readme.style`,
  `readme.language`, `suggestions.modularity`, `suggestions.filter`,
  `suggestions.naming`, `prompt.directives`).
- Una preferencia **no puede ampliar permisos** ni silenciar categorías
  `security`.
- Todo cambio queda en `audit.log` y se puede revertir con `/prefs rm`.

## Commits y pull requests

- Un commit = un cambio coherente. Mensajes en imperativo: `feat:`, `fix:`,
  `docs:`, `test:`, `refactor:`.
- Describe el *porqué* en el cuerpo del commit o del PR.
- Incluye la salida de `pytest` y `ruff` cuando aplique.
- Los cambios de comportamiento deben actualizar
  `documentation/EPITAPH_DOCUMENTO_TECNICO.md`.

## Issues

- `good first issue`: acotado, con pistas y sin dependencias ocultas.
- `bug`: incluye pasos de reproducción, versión de Python, sistema y modelo.
- `enhancement`: explica el caso de uso antes de proponer la solución.

## Licencia

Al contribuir aceptas que tu aporte se publique bajo la licencia MIT del
proyecto.
