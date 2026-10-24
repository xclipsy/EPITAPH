# Changelog

Todas las versiones relevantes de EPITAPH. Formato basado en
[Keep a Changelog](https://keepachangelog.com/es/1.1.0/) y versionado
[SemVer](https://semver.org/lang/es/).

## [No publicado]

### Añadido

- Chat interactivo con comandos y captura de preferencias en lenguaje natural.
- Respuesta del chat en streaming (token a token) con métricas de `tok/s`, primer
  token y tiempo total; `Ctrl+C` interrumpe la generación sin cerrar la sesión.
- `epitaph describe [carpeta]`: describe cualquier proyecto sin configurarlo
  (`--json`, `--md`, `--out`), reutilizando el análisis determinista y la prosa
  opcional del modelo local.
- Precarga del modelo del chat en segundo plano (`warmup`) para que la primera
  pregunta no espere a la carga.
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

### Cambiado

- Análisis hasta 4× más rápido: el escáner poda directorios ignorados (`.venv`,
  `node_modules`, …) y deja de llamar `resolve()` por archivo.
- Los lenguajes sin AST nativo (Java, JS/TS, Go, Rust, PHP, Ruby, C#, shell)
  ahora reportan clases y funciones en lugar de cero.
- El cliente de Ollama reutiliza una sola conexión y cachea la sonda y la lista
  de modelos, evitando viajes HTTP redundantes por mensaje.

## [0.1.0]

Primera versión alpha del núcleo demostrable.
