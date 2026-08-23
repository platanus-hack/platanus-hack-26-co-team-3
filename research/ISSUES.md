# Problemas encontrados — leer antes del freeze de las 9am

Encontrados de madrugada (2026-08-23, ~01:00) revisando el merge de Andrés
y probando los servicios desplegados. **Los dos están verificados con
pruebas reales, no son sospechas.**

Ninguno lo toqué: los dos viven en bloques que no son míos
(`roxy-gateway` = Stiven, `verifier` = Sebastián/Andrés). Dejo el
diagnóstico y el arreglo propuesto para que lo apliquen en segundos.

---

## 1. 🔴 CRÍTICO — `verifier/evaluator.py` no habla el mismo idioma que el gateway

**Impacto si no se arregla:** si alguien apunta `EVALUATOR_URL` al
evaluador de Python, **toda la corrida "con Roxy" falla** (503). Es
justo la mitad de la demo.

**Estado hoy:** en producción NO está pasando, porque `EVALUATOR_URL`
apunta al motor de Rust de Sebastián, que sí habla el contrato correcto.
O sea: **la demo hoy funciona**. Pero cualquiera que siga el
`verifier/README.md` al pie de la letra rompe la demo sin darse cuenta.

### La prueba

Levanté `verifier/evaluator.py` en local y le mandé exactamente lo que
manda `roxy-gateway/internal/policy/remote.go`:

```bash
# Lo que el gateway MANDA hoy:
curl -X POST localhost:9010/evaluate \
  -d '{"rules":["..."],"prompt":"update_invoice: ..."}'
→ HTTP 422  {"detail":[{"loc":["body","mcp"],"msg":"Field required"}, ...]}

# Lo que evaluator.py ESPERA:
curl -X POST localhost:9010/evaluate \
  -d '{"mcp":{...},"request":{...},"time":"..."}'
→ HTTP 200  {"allowed":false,"violatedPriority":1,"reason":"proposedTotal (0) no coincide..."}
```

El gateway trata cualquier respuesta que no sea 2xx como
`ErrUnavailable` → le devuelve **503** al agente.

### Dónde está el desacuerdo

| lado | archivo | forma |
|---|---|---|
| gateway (manda) | `roxy-gateway/internal/policy/remote.go:30-33` | `{rules: string[], prompt: string}` |
| evaluador Rust (recibe) ✅ | `verifier/engine/src/service.rs:373` | `{rules, prompt}` — **coincide** |
| evaluador Python (recibe) ❌ | `verifier/evaluator.py:29` | `{mcp, request, time}` — **no coincide** |
| README de verifier | `verifier/README.md:15` | documenta `{mcp, request, time}` — **desactualizado** |

### Arreglo propuesto (el más seguro: aceptar las dos formas)

En `verifier/evaluator.py`, hacer `mcp` y `request` opcionales y aceptar
también `{rules, prompt}`. Así funciona con el gateway tal como está hoy
**y** con lo que documenta el README — sin tocar el Go de Stiven ni
romper nada de lo que ya anda.

Idea concreta (no aplicada):

```python
class EvaluateRequest(BaseModel):
    # forma A (la que documenta el README)
    mcp: Optional[Dict[str, Any]] = None
    request: Optional[Attempt] = None
    time: Optional[str] = None
    # forma B (la que el gateway manda HOY)
    rules: Optional[List[str]] = None
    prompt: Optional[str] = None
```

y en `evaluate()`, si viene `prompt` en vez de `request`, parsear el
payload desde ahí (el gateway arma el prompt como
`"<action>: <intent>"`, ver `agentPrompt()` en `remote.go:122`).

**Ojo:** el evaluador de Python decide mirando campos del payload
(`proposedTotal`, `computedSubtotalSum`, `appendsAuditLog`). El gateway,
al aplanar todo a un `prompt` de texto, **pierde esos campos
estructurados**. Con la forma B el evaluador de Python no puede decidir
igual de bien — es una limitación real del contrato `{rules, prompt}`,
no un bug del evaluador. Vale la pena decidir en equipo si el contrato
correcto no debería ser el estructurado.

---

## 2. 🟠 Cada decisión se registra DOS veces → el dashboard muestra todo duplicado

**Impacto:** en la vista de Logs (que es parte del demo), cada decisión
aparece dos veces. Se ve descuidado justo en la pantalla que más se
muestra.

### La prueba

Logs reales de producción, mismo timestamp, mismo agente, misma
descripción, dos `_id` distintos:

```json
{"_id":"6a8a8dea55b8bae8f56f80f4", "accessedBy":"agent-subtask-INV-1011",
 "action":"update_invoice", "time":"2026-08-23T06:06:34.972000", ...}
{"_id":"6a8a8dea4da496777dc3781a", "accessedBy":"agent-subtask-INV-1011",
 "action":null,             "time":"2026-08-23T06:06:34.972000", ...}
```

### Causa raíz

`roxy-gateway/internal/gateway/service.go` escribe el log **dos veces**:

- línea 94: `s.logs.Insert(...)` → escribe directo a Mongo `security`
- línea 106: `s.notifier.Notify(...)` → `POST DASHBOARD_URL` (`/api/log`)
  → **la API del dashboard inserta en la misma colección `security`**

La diferencia entre las dos filas: el struct Go `security.Log`
(`internal/security/model.go`) **no tiene campo `Action`**, así que la
escritura directa deja `action: null`; la que pasa por `POST /log` sí lo
lleva.

### Arreglo

Dos opciones, la primera es la buena:

1. **En el gateway (raíz):** quitar una de las dos escrituras. Si el
   dashboard ya persiste vía `POST /log`, la escritura directa a Mongo
   sobra (y encima pierde `action` y `violatedRule`). Es 1 línea.
2. **En el dashboard (parche):** deduplicar al leer. Lo dejé **listo pero
   no activado** — ver abajo.

**Mitigación que sí dejé aplicada** (es mi bloque, es seguro): la vista de
Logs deduplica al leer, agrupando por
`(time, accessedBy, mcpId, description)` y quedándose con la fila más
completa. No borra nada de Mongo — solo evita mostrar la misma decisión
dos veces. Si arreglan la raíz en el gateway, esto sigue funcionando
igual (no hay duplicados que agrupar).

---

## 3. 🟡 Menor — `violatedRule` llega `null` en las denegaciones

En los logs reales, las filas `denied` traen `violatedRule: null`. El
motivo sí está, pero embebido en el texto de `description`
(`"...denied by rule priority 1"`).

**Por qué importa para el demo:** el drawer del dashboard muestra la
regla violada como campo estructurado. Con `violatedRule: null`, ese
campo no aparece y se pierde el "¿por qué exactamente?" — que es
justamente lo más contundente para el jurado (leer la regla en español
que el agente intentó violar).

No lo arreglé porque el origen está en el gateway. Si Stiven puede
poblar `violatedRule` con la regla que gobernó, el dashboard ya lo
muestra sin cambios.
