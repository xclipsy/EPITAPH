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

## [0.1.0]

Primera versión alpha del núcleo demostrable.
