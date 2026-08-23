# roxy-guard

Trazabilidad y control de acceso para flujos de agentes que consumen MCPs.

Cuando un agente delega en otro, y ese en otro, el que termina tocando la
base de datos está a varios saltos de quien pidió la tarea. Este SDK
registra esa cadena mientras ocurre y somete cada acción sensible al
veredicto de Roxy antes de que se ejecute.

## Instalación

```bash
pip install roxy-guard
# o
uv add roxy-guard
```

El paquete se instala como `roxy-guard` y se importa como `roxy` (igual que
`pillow` → `import PIL`). El nombre corto ya estaba tomado en PyPI.

## CLI

Al instalarlo queda el comando `roxy`. Apunta al despliegue público por
defecto; `ROXY_API_URL` lo cambia.

```bash
roxy check                  # ¿responden dashboard, demo-api y gateway?
roxy runs                   # últimas corridas de agentes
roxy tree <sessionId>       # el árbol de delegación de una corrida
roxy logs --denied          # solo lo que Roxy bloqueó
roxy audit reglas.json      # Z3 sobre tus reglas: ¿hay algún hueco?
```

`--json` en cualquiera devuelve la respuesta cruda, para encadenar con `jq`.

`roxy audit` es el único que necesita el verificador levantado
(`--engine` o `ROXY_ENGINE_URL`): no está expuesto en el despliegue público.
Sale con código 1 si encuentra un hueco, así que sirve en CI.

## Qué funciona sin montar nada

| | necesita |
|---|---|
| Trazabilidad (el árbol) | solo `api_url` — funciona contra el despliegue público |
| `roxy check` / `runs` / `tree` / `logs` | nada, apuntan al despliegue |
| Control de acceso (`guard()`) | un gateway **y** un MCP registrado con sus reglas |
| `roxy audit` | el verificador corriendo |

## Uso

Se engancha una vez, en la invocación. Los agentes no se tocan.

```python
from roxy import Roxy

roxy = Roxy(api_url="https://roxygt.lat/api")

executor.invoke(
    {"input": "concilia las facturas pendientes"},
    config={"callbacks": [roxy], "metadata": {"purpose": "conciliación mensual"}},
)

print(roxy.tree())  # el árbol completo, como lo ve el dashboard
```

Cada agente que se lance dentro de esa invocación queda registrado solo,
con su padre correcto. No hay ids que pasar de mano en mano.

### Sub-agentes en invocaciones separadas

Un sub-agente lanzado con su propio `.invoke()` llega sin padre — LangChain
no puede encadenar dos invocaciones independientes. `child_config` arma la
config con el padre ya declarado:

```python
executor.invoke(entrada, config=roxy.child_config(run_id_del_padre,
                                                  purpose="conciliar INV-1005"))
```

### Control de acceso

```python
from roxy import RoxyUnavailable

try:
    decision = roxy.guard(
        action="update_invoice",
        payload={"invoiceId": "INV-1005", "proposedTotal": 0,
                 "computedSubtotalSum": 600000},
        run_id=run_id,
        mcp_name="invoices-mcp",
    )
except RoxyUnavailable:
    return  # sin veredicto no hay permiso

if not decision.allowed:
    return f"denegado: {decision.reason}"
escribir_en_la_base()
```

`RoxyUnavailable` no es una negación ni un permiso: significa que Roxy no
pudo decidir. Tratarlo como permiso sería conceder acceso justamente
porque la capa de seguridad se cayó.

### Delegación entre procesos (A2A)

Cuando el sub-agente corre en otro proceso, la cadena se propaga por
headers:

```python
# quien delega
requests.post(url_del_subagente, json=tarea, headers=roxy.headers_to_send(run_id))

# quien recibe
roxy.receive(request.headers, ejecutar_subagente, tarea)
```

Sin esto el agente remoto arranca un árbol nuevo y la cadena se corta justo
donde importa: en el salto entre organizaciones.

### Auditoría

```python
roxy.lineage(agent_id)   # de la raíz hasta ese agente
roxy.tree()              # todos los nodos de la sesión
```

## Cómo funciona por dentro

`Roxy` hereda de `BaseCallbackHandler`, así que LangChain le avisa cada vez
que arranca un chain. En cada aviso el SDK decide si ese chain es un agente
que vale la pena registrar y, si lo es, hace `POST /agents`.

Hay dos detalles que resuelve por su cuenta:

**Traducción de ids.** LangChain identifica cada run con un UUID; la API de
Roxy asigna un ObjectId de Mongo y valida que `parentId` sea uno de los
suyos. El SDK mantiene el mapa `run_id → id de Roxy` y traduce, porque el
id del framework no sirve como padre.

**Filtrado de ruido.** Una corrida de cuatro agentes dispara unos noventa
eventos: prompts, parsers, scratchpads. Registrarlos todos convertiría el
árbol en ruido. Se registra un nodo cuando la invocación trae `purpose` en
su metadata o cuando el chain es un `AgentExecutor`.

Todo el registro es *fail-open*: si la API no responde, se pierde el nodo y
el agente sigue. La traza es observación, no la tarea. El control de acceso
es lo contrario, *fail-closed*: sin veredicto no se ejecuta nada.

## Licencia

MIT
