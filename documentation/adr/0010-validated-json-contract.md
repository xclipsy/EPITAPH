# ADR-010 — Contrato JSON validado

## Contexto

El modelo es una fuente no confiable: puede devolver Markdown, texto libre, JSON
parcial o instrucciones inyectadas desde el repositorio.

## Decisión

El proveedor devuelve texto; EPITAPH extrae y valida JSON contra un esquema
`pydantic` (`ProsePayload`, `PreferenceProposal`). Las rutas de `module_notes` se
filtran contra los hechos: una nota que apunta a un archivo inexistente se
descarta. El modelo nunca escribe archivos ni ejecuta comandos.

Si la validación falla, se reintenta una vez y luego se usa la plantilla
determinista.

## Consecuencias

- La salida del modelo es datos, no instrucciones.
- Un cambio de prompt no puede saltarse permisos ni el merge.
- Los tests pueden simular respuestas inválidas sin Ollama.
