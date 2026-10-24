# Changelog

Todas las versiones relevantes de EPITAPH. Formato basado en
[Keep a Changelog](https://keepachangelog.com/es/1.1.0/) y versionado
[SemVer](https://semver.org/lang/es/).

## [No publicado]

### Añadido

- Chat interactivo con comandos y captura de preferencias en lenguaje natural.
- Preferencias confirmadas y persistentes en `.epitaph/preferences.toml`
  (`readme.structure`, `readme.style`, `readme.language`,
  `suggestions.modularity`, `suggestions.filter`, `suggestions.naming`,
  `prompt.directives`).
- Wizard de primera ejecución con selección de funciones, cadencia, modelo y
  permisos.
- Selector de modelos por rol con detección de hardware y recomendación de RAM.
- Análisis determinista: lenguajes, árbol, dependencias, ciclos, huérfanos,
  puntos de entrada, métricas y secretos.
- README por marcadores con merge por fingerprint e idempotencia.
- `requirements.suggested.txt` y `suggestions.md` con deduplicación y ciclo de
  vida.
- Permisos, backups, `undo`, auditoría append-only y guarda de git limpio.
- `doctor`, `bench`, `analyze`, `watch` y `--dry`.
- Preflight de Ollama: los comandos que requieren modelo se bloquean con un
  panel de diagnóstico si `ollama serve` no responde; `--no-llm` mantiene el
  camino determinista.
- Diagnóstico `doctor` en tabla estructurada.
- Interfaz de terminal rediseñada con el lenguaje visual de PRAXIA CLI: banner en
  panel, panel de sesión, `/help` como tabla, entrada enmarcada por reglas,
  autocompletado de comandos slash, respuestas en Markdown con streaming y
  salidas estructuradas para el resto de comandos.
- Quick start end-to-end en el README.

### Corregido

- El guard de git ignora los artefactos propios (`.epitaph/`, `suggestions.md`,
  `requirements.suggested.txt`, `README.suggested.md`), de modo que `init` no
  bloquea el primer `update`.

## [0.1.0]

Primera versión alpha del núcleo demostrable.
