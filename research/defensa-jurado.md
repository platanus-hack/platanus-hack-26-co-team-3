# Defensa ante el jurado

Preguntas que van a hacer, con la respuesta honesta y dónde verificarla.
La regla: **nunca defender algo que no aguante un `curl`.** Si algo no
funciona, decirlo antes de que lo encuentren — encontrarlo ellos cuesta
mucho más que admitirlo nosotros.

---

## Lo que un agente de jurado puede concluir mal

Los jurados técnicos analizan el repo con agentes. Un agente lee de arriba a
abajo y no pregunta. Esto ya nos pasó: otra instancia de IA concluyó que
*"Roxy y el verificador son dos productos distintos sin integrar"* y que el
evaluador real eran *"dos `if` en Python"*.

**Era falso, y la evidencia estaba a un `curl` de distancia.** Pero el repo
lo sugería. Corregido el 2026-08-23:

| archivo | qué sugería | estado |
|---|---|---|
| `verifier/README.md` | abría presentando `evaluator.py` (2 `if`) como la implementación y decía "lo que falta es Z3" | ✅ reescrito: abre con cuál corre en producción y cómo verificarlo |
| `evaluator.py` (docstring) | se describía como "la capa de verificación" | ✅ ahora dice "fallback local, NO es la implementación" |
| `idea.md` | 6 de 10 bloques sin marcar, incluidos los que corren en prod | ✅ actualizado con lo verificado |
| `README.md` raíz | era la plantilla del hackathon sin llenar | ✅ reemplazado |

**Cómo se refuta en 30 segundos si vuelve a salir:**

```bash
curl -s "https://roxygt.lat/api/log?limit=40" | grep -o "operation [0-9].*"
```

Cada evaluador deja una firma distinta en `description`. `operation N (...)
is denied by rule priority N` viene de `verifier/engine/src/engine.rs:114` —
el motor de Rust. 18 de 19 denegaciones en producción son suyas.

---

## Preguntas técnicas duras

### "¿Esto no es solo un LLM vigilando a otro LLM?"

No, y es la pregunta correcta. Un LLM traduce las reglas en lenguaje natural
a una política formal **una sola vez**. La decisión corre sobre esa política
congelada y hasheada, sin LLM en el camino: mismo input, mismo veredicto,
byte por byte.

Encima, Z3 audita el **conjunto de reglas** — algo que ningún LLM puede
hacer: *¿existe alguna acción destructiva que se cuele por las reglas que
escribiste?* Si la hay, devuelve el contraejemplo exacto.
`verifier/engine/src/z3enc.rs`, `POST /audit`.

### "¿Roxy no es un punto único de falla? Está en el camino crítico e inyecta credenciales."

Sí, y es un trade-off consciente, no un descuido. Es la misma posición que
ocupa cualquier API gateway o service mesh: para poder negar hay que estar en
el camino.

Lo que hicimos al respecto:
- **Falla cerrado.** Si Roxy no puede emitir veredicto, no hay permiso. El
  SDK levanta `RoxyUnavailable` en vez de asumir "allow"
  (`roxy-sdk/src/roxy/client.py`).
- **Las credenciales nunca vuelven al agente.** Roxy las usa para llamar al
  MCP; el agente recibe la respuesta, nunca el secreto.
- **Cada decisión queda anclada fuera de nuestro control** (Solana), así que
  un Roxy comprometido no puede reescribir su propio historial.

Lo que **no** resolvimos: si comprometés el proceso de Roxy, tenés las
credenciales de los MCPs. Mitigarlo de verdad es rotación por petición y
aislamiento del almacén de secretos. No está hecho.

### "¿Cuánta latencia agrega?"

No tenemos un benchmark serio y no vamos a inventar uno. Lo medible hoy:
`/gateway/health` responde en ~200 ms end-to-end desde fuera de AWS, pero eso
mide CloudFront + red, no el costo de la decisión.

Lo estructural sí lo podemos afirmar: la compilación de reglas (el paso con
LLM) está **cacheada** — se paga una vez por conjunto de reglas, no por
petición (`CachingCompiler` en `engine/src/compiler.rs`). La evaluación
posterior es determinista y local.

### "¿Por qué devnet y no mainnet?"

Porque es un hackathon y anclar en mainnet cuesta plata real sin agregar nada
a la demostración. Está marcado `DEVNET ONLY` en cada archivo del attestor —
preferimos eso a insinuar producción. La mecánica (derivar la PDA, firmar,
anclar) es idéntica.

### "¿Está todo realmente integrado o son piezas sueltas?"

Integrado: agente → SDK → gateway → verificador → MCP → log → dashboard. Se
verifica corriendo `agent-flow-demo/compare.sh`, que ejecuta el mismo flujo
con y sin Roxy contra el despliegue real.

**No integrado, y lo decimos:** el attestor de Solana se orquesta desde el
SDK del verificador, no desde el camino del gateway. Z3 sí corre dentro de
`/evaluate` (`engine/src/service.rs:317`); la atestación on-chain hoy es un
flujo aparte.

### "¿Qué pasa si el evaluador se cae?"

El gateway devuelve 503 y el SDK levanta excepción. Ninguna acción se ejecuta
sin veredicto. Es la decisión correcta para una capa de seguridad: preferir
que el agente falle a que pase de largo.

---

## Lo que hay que decir antes de que lo encuentren

Está todo en [`ISSUES.md`](ISSUES.md), con evidencia reproducible:

1. **CloudFront convierte cada denegación (403) en un `200` con el HTML del
   dashboard.** Roxy deniega y registra bien server-side, pero el agente ve
   un error en vez de "denegado". Si en la demo aparece "Roxy no
   disponible", es esto — no es que Roxy no funcione.
2. **Cada decisión se registra dos veces** (el gateway escribe directo a
   Mongo *y* vía `POST /log`). Mitigado en el dashboard al leer.
3. **`verifier/evaluator.py` no habla el contrato del gateway.** No afecta
   producción — ahí corre el motor de Rust — pero está ahí.

Publicar esta lista es a favor nuestro: un equipo que sabe exactamente qué
no funciona demuestra más control que uno que dice que todo funciona.

---

## Desempate: por qué nosotros

Si están comparando cabeza a cabeza:

- **Profundidad técnica.** Cuatro lenguajes en producción (Go, Rust, Python,
  TypeScript) sobre AWS con Terraform. Verificación formal con Z3 y
  atestación on-chain — cosas que casi no se ven en un hackathon.
- **Honestidad verificable.** Todo lo que afirmamos se comprueba con un
  `curl` público, y publicamos nuestros propios defectos con evidencia.
- **La demo muestra daño real.** No narramos que algo *no* pasó: mostramos la
  factura corrompida, con su `409`, y después la misma corrida intacta.
  Enseñar el daño es más contundente que contar su ausencia.
- **Timing.** A2A tiene 16 meses. Ni Workday llegó a producción en gobernanza
  de agentes (acceso anticipado, 2do semestre 2026). El problema todavía no
  tiene incumbente — ver [`existing-solutions.md`](existing-solutions.md).

**Dónde somos más débiles:** onboarding y pulido de producto terminado. No
tenemos instalador ni flujo de alta. Si preguntan, esa es la respuesta —
no inventar uno.
