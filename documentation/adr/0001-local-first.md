# ADR-001 — Local-first

## Contexto

El código analizado puede ser privado. Enviarlo a un servicio remoto introduce
coste, latencia, dependencia de terceros y una superficie de fuga de secretos.

## Decisión

Ollama es el backend por defecto y corre en `localhost`. No hay claves de API,
telemetría ni llamadas externas en el flujo normal. Un backend remoto solo se
permite si el usuario lo configura explícitamente y el wizard avisa.

## Consecuencias

- La calidad depende del hardware del usuario; el selector de modelos y `bench`
  lo hacen visible.
- Sin red, la herramienta sigue siendo útil: el análisis es determinista.
- El contrato de proveedor es abstracto para poder añadir `llama.cpp` sin
  cambiar el pipeline.
