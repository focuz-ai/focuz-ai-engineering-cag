# CAG con contexto y caché

Autor: [Focuz](https://www.focuz.io/). Ejemplo de las sesiones 01 a 05.
Python 3.11 o posterior. La ejecución predeterminada usa solo la biblioteca estándar.

## Ejecutar

Desde la carpeta del repositorio:

```powershell
python -m unittest discover -s tests -v
python -m cag
```

La demo imprime dos objetos JSON: `cache_hit` es `false` y luego `true`.
La respuesta contiene la política ficticia de A y `source=policy-A-v2`.

## Qué demuestra

El conocimiento autorizado se precarga en el contexto, como enfoque CAG.
Además se guarda una caché de respuestas por usuario, tenant, roles, contenido,
versión, modelo, prompt y pregunta. Esta caché de aplicación NO es KV/prefix caching.
Los permisos se verifican antes de consultar la caché. El baseline es extractivo;
sus resultados no miden capacidad de un LLM.

El límite de caracteres ilustra un presupuesto; producción necesita contar tokens
con el tokenizer del modelo, reservar salida y manejar concurrencia y memoria.
El bloqueo global evita carreras en el ejemplo, pero limita throughput.
Los roles se construyen en la demo: un servicio real debe obtenerlos de identidad
verificada en servidor. Un cliente no puede autoasignarse tenant ni rol.

## Extensión opcional con API real

`cag/openai_provider.py` implementa un adaptador Responses con JSON Schema [1].
Configura `OPENAI_API_KEY` y `LLM_MODEL` fuera del repositorio en un terminal privado,
seleccionando un modelo compatible con Structured Outputs en tu cuenta. Luego:

```powershell
python -m cag --live
```

Esta opción puede generar coste. No se llama en la demo ni en CI. Las pruebas
del adaptador usan un transporte falso y no verifican credenciales, cuota, calidad
ni compatibilidad de un modelo real. No pegues secretos en commits o capturas.
El parámetro `store=False` no constituye una garantía de ausencia de retención;
revisa las condiciones del proveedor. No se implementan reintentos para evitar
ocultar presupuesto y políticas de error durante el primer laboratorio.

## Laboratorio

1. Ejecuta la demo y explica cuándo se invoca el proveedor.
2. Cambia el contenido manteniendo la versión y verifica invalidación.
3. Añade un usuario B y demuestra que la política A no llega al proveedor.
4. Simula timeout e incompletitud; verifica que no se cachean errores.
5. Diseña una caché distribuida con límites por tenant y un contador de tokens.

Entrega pruebas y un ADR CAG frente a RAG. Aprobar requiere aislamiento y una
respuesta de abstención cuando falta evidencia, además de la ruta feliz.

## Fuentes

[1] https://developers.openai.com/api/docs/guides/structured-outputs
[2] https://developers.openai.com/api/docs/quickstart
[3] https://www.lidr.co/ai-engineering/ (estructura curricular)

Consulta del manual: 28 de octubre de 2026. Los ejemplos de API cambian; contrasta
el contrato antes de usarlos en un entorno real. Véase NOTICE.md para el alcance.
