# ADR-006 — `requirements.txt` nunca se modifica solo

## Contexto

Un import detectado no siempre implica una dependencia directa: puede ser
opcional, transitiva, específica de plataforma o resuelta con un alias ambiguo.
Añadir o quitar líneas automáticamente puede romper el proyecto.

## Decisión

EPITAPH genera `requirements.suggested.txt` con las dependencias declaradas, las
faltantes detectadas y las declaradas sin uso (comentadas). Muestra el diff y no
toca `requirements.txt` salvo permiso explícito `write:requirements = allow` y
confirmación.

## Consecuencias

- El usuario conserva el control de versiones y extras.
- Los alias ambiguos se marcan como `# revisar: ...` en lugar de adivinar.
- La decisión queda registrada en el informe de sugerencias.
