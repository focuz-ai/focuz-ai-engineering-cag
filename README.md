# CAG con contexto y caché

Autor: [Focuz](https://www.focuz.io/). Ejemplo de las sesiones 01 a 05.
Python 3.11 o posterior. La ejecución predeterminada usa solo la biblioteca estándar.
Versión del ejemplo: 1.1.0.
Repositorio: https://github.com/focuz-ai/focuz-ai-engineering-cag

## Ejecutar

Desde la carpeta del repositorio:

```powershell
python -m unittest discover -s tests -v
python -m cag
python -m cag.decisions
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

El contexto vacío o compuesto solo por espacios se rechaza con `ValueError` antes
de llamar al proveedor. Una respuesta sin texto visible también se rechaza antes
de insertarla en la caché, incluso si declara `abstained=true`: una abstención
válida debe explicar que no hay evidencia. Esto evita confundir un error de
entrada o de formato con una respuesta fundamentada.

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

El adaptador conserva estados distintos mediante excepciones de
`cag.openai_provider`, todas compatibles con `RuntimeError`:

| Resultado | Excepción | Conducta |
| --- | --- | --- |
| `completed` con contenido `refusal` | `ProviderRefusalError` | Rechazo explícito; no es una abstención por falta de evidencia |
| `incomplete` | `IncompleteResponseError` | Respuesta incompleta; no se acepta texto parcial |
| Sobre o JSON inválido, campos incorrectos o texto en blanco | `InvalidResponseError` | Error de contrato; no se acepta como éxito |
| Otro estado no completado | `ProviderResponseError` | Fallo del proveedor; no se etiqueta como incompleto |

Ninguna de estas excepciones añade resultados a la caché. Sus mensajes no incluyen
el texto recibido del proveedor. Las pruebas usan por separado un sobre oficial
`completed/refusal`, otro `incomplete`, JSON inválido y respuestas en blanco.
Una prueba local de esos contratos no acredita una llamada real a OpenAI.

## Decisión tipada y política independiente (1.1.0)

`cag.decisions.decide(probabilities, allowed_actions, threshold=0.8, min_margin=0.2)`
recibe exactamente `answer/retrieve/human`, valida números finitos en [0,1] y suma
1 con tolerancia absoluta 1e-9. Usa `p_max` y diferencia entre las dos primeras
probabilidades. Empates, poca separación o una acción no autorizada devuelven
`human` con `abstained=true`; no ejecuta acciones. La política `allowed_actions`
la aporta el servidor y no el modelo. La salida tipada nunca otorga permisos.

El umbral y el margen son inclusivos. Para evitar artefactos de resta binaria,
las comparaciones usan el valor decimal de `str` de los números recibidos en un
contexto local independiente: 0.6 frente a 0.4 cumple un margen mínimo de 0.2.
No se añade un epsilon: un umbral o margen estrictamente mayor sigue rechazando
el candidato. Los empates continúan produciendo abstención, incluso con umbral
y margen cero. Esta semántica corrige la falsa abstención de frontera detectada
en la revisión independiente de la edición 1.1.0.

La demo imprime una decisión aceptada (p_max 0.9) y una abstención (0.45 frente
a 0.4). Son distribuciones sintéticas, no inferencia, calibración ni una prueba
de Jev, Laya o Clef. El umbral 0.8 y margen 0.2 son opciones docentes que requieren
calibración con datos propios. `p_max` no es el campo `confidence` de Jev.
Su documentación distingue esa confianza de la probabilidad máxima.

La versión 1.1.0 también cierra A2-CODE-01: JSON externo malformado y bytes con
codificación inválida producen `InvalidResponseError` sin contenido del proveedor
en el mensaje. Las regresiones atraviesan `json.load` con cuerpos binarios; HTTP,
timeout, refusal e incompletitud conservan sus categorías. Ningún error se cachea.

## Laboratorio

1. Ejecuta la demo y explica cuándo se invoca el proveedor.
2. Cambia el contenido manteniendo la versión y verifica invalidación.
3. Añade un usuario B y demuestra que la política A no llega al proveedor.
4. Simula timeout, rechazo explícito, incompletitud y salida en blanco; comprueba
   que el consumidor distingue las causas y que no se cachean errores. Prueba
   también contexto vacío antes de invocar el proveedor.
5. Diseña una caché distribuida con límites por tenant y un contador de tokens.

Entrega pruebas y un ADR CAG frente a RAG. Aprobar requiere aislamiento y una
respuesta de abstención cuando falta evidencia, además de la ruta feliz.

## Fuentes

[1] https://developers.openai.com/api/docs/guides/structured-outputs
[2] https://developers.openai.com/api/docs/quickstart
[3] https://www.lidr.co/ai-engineering/ (estructura curricular)

Consulta del manual: 28 de octubre de 2026. Los ejemplos de API cambian; contrasta
el contrato antes de usarlos en un entorno real. Véase NOTICE.md para el alcance.
El contrato `completed/refusal` de [1] se volvió a contrastar el 1 de noviembre
de 2026 al corregir TECH-02 y TECH-03. Se ejecutaron pruebas y demo locales con
transporte simulado; no se realizó una llamada facturable.

Fuentes complementarias del workshop, consultadas el 2 de noviembre de 2026:

- https://lidr.notion.site/material-workshop-ai-engineer-pro
- https://docs.typesafe.ai/introduction
- https://docs.typesafe.ai/confidence

El ejemplo de decisión es una implementación original de Focuz de un contrato
de validación. Para usar un proveedor real se necesita un adaptador explícito,
autenticación, evaluación y política de abstención; no se incluye una conexión
a esos modelos en este laboratorio.
