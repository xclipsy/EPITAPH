# EPITAPH

> Documentación viva, local y no destructiva.

EPITAPH mantiene el `README.md` de tu proyecto sincronizado con el código. Analiza la
arquitectura de forma determinista (árbol, dependencias, ciclos, código muerto y puntos de
entrada), redacta únicamente lo que no se puede derivar y fusiona el resultado por secciones
delimitadas, sin tocar el texto escrito por humanos.

Funciona con modelos locales (Ollama / llama.cpp): sin claves de API, sin telemetría y sin
enviar tu código a terceros. Si nada cambió, no llama al modelo y no produce ningún diff.

## Quick start

```bash
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"

epitaph init            # funciones, cadencia, modelo y permisos
epitaph update --dry    # propuesta de README, sin escribir nada
epitaph update --yes    # aplica los cambios
epitaph                 # chat interactivo
```

Sin modelo local también funciona: el análisis es determinista.

```bash
epitaph update --no-llm
```

Para prosa generada, instala Ollama y un modelo de código:

```bash
ollama pull qwen2.5-coder:3b
epitaph doctor
```

## Estado

Alpha (`0.1.0`). La especificación completa está en
[`documentation/EPITAPH_DOCUMENTO_TECNICO.md`](documentation/EPITAPH_DOCUMENTO_TECNICO.md).

## Requisitos

- Python 3.12+
- Git (recomendado: el guard de árbol limpio lo usa)
- Opcional: [Ollama](https://ollama.com) para la prosa

## Uso

```bash
epitaph init          # configuración guiada (funciones, cadencia, modelo, permisos)
epitaph               # chat interactivo
epitaph update --dry  # propuesta de README sin escribir
epitaph analyze       # hechos del proyecto en JSON
epitaph prefs         # preferencias confirmadas
epitaph structure     # estructura efectiva del README
epitaph doctor        # diagnóstico del entorno
```

Dentro del chat:

```
/update --dry
/models
/every 10m
/prefs
> prefiero el árbol al final y sin badges
```

Las preferencias en lenguaje natural se convierten en una propuesta, se confirman y se
persisten en `.epitaph/preferences.toml`. Nunca amplían permisos ni desactivan la seguridad.

## Cómo funciona

```text
autosave → watcher → debounce/intervalo → análisis determinista
        → ¿cambió el fingerprint? ──no──→ sin diff, 0 tokens
                                  └─sí──→ modelo local (solo prosa)
                                        → merge por marcadores
                                        → permisos + git limpio + backup
                                        → escritura atómica + auditoría
```

- **Determinista primero**: versiones, comandos, árbol y dependencias salen del análisis.
- **Incremental**: solo se reescriben las secciones cuyo contenido cambió.
- **No destructivo**: `--dry`, backups, `undo` y verificación de git.
- **Local**: el modelo nunca escribe archivos; devuelve JSON validado.

## Desarrollo

```bash
uv run pytest
uv run ruff check .
```

## Documentación

- [Especificación técnica](documentation/EPITAPH_DOCUMENTO_TECNICO.md)
- [Decisiones de arquitectura (ADR)](documentation/adr/)
- [Guía de contribución](CONTRIBUTING.md)
- [Changelog](CHANGELOG.md)

## Licencia

MIT — ver [`LICENSE`](LICENSE).
