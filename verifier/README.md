# verifier

Bloque 10 (idea.md): la capa de verificación que Roxy consulta antes de dejar
pasar una petición. Responde, para cada regla del MCP, la pregunta del
diseño: *este contexto de petición, ¿se encuentra bajo lo que rige esta
regla?*

## Contrato

Lo fija el gateway (`roxy-gateway/internal/policy/remote.go`). No cambia
cuando la verificación pase a Z3:

```
POST /evaluate
  entra {"mcp": {id, name, description, rules}, "request": {accessedBy, action, payload}, "time"}
  sale  {"allowed": bool, "violatedPriority": int|null, "reason": str}
```

`violatedPriority` es la prioridad de la primera regla que aplique: el
gateway reporta una sola.

## Correr

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn evaluator:app --port 9000
```

Y en el gateway: `EVALUATOR_URL=http://localhost:9000/evaluate`.

## Tests

```bash
python3 -m pytest tests/ -q
```

7 tests, sin nada levantado.

## Estado

`evaluator.py` comprueba a mano los dos invariantes de facturación que hoy
usa la demo (el total tiene que cuadrar con las líneas; cerrar como `paid`
exige registro de auditoría). Es lo mínimo para que el gateway tenga a quién
preguntarle. Lo que falta es el trabajo del bloque: traducir reglas y
contexto de lenguaje natural a Z3 y resolver ahí, en vez de tener las
comprobaciones escritas una por una.
