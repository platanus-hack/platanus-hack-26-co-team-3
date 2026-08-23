# demo-api

API de facturación que sirve como **víctima** en la demo de Roxy. No tiene
lógica de seguridad ni conoce a Roxy: es la API normal de una empresa
cualquiera, que expone su estado de consistencia para que la corrupción de
datos hecha por el flujo de agentes (Bloque 5) sea visible de inmediato.

## Stack

Python 3.11 + FastAPI + pymongo (sin ORM/ODM). Puerto `8001`.

## Cómo correr

```bash
cd demo-api
cp .env-example .env   # ajustar MONGO_URI/DB_NAME si hace falta
./run.sh
```

`run.sh` crea un virtualenv, instala `requirements.txt` y levanta la API con
`uvicorn` en `http://localhost:8001`. Al arrancar, si la colección
`invoices` está vacía, la siembra automáticamente desde
`seed/invoices.seed.json` (no hace falta un paso manual de seed).

Requiere una instancia de MongoDB corriendo y alcanzable en `MONGO_URI`.

## Docker

```bash
cd demo-api
docker build -t demo-api .
docker run -p 8001:8001 \
  -e MONGO_URI=mongodb://host.docker.internal:27017 \
  -e DB_NAME=demo_billing \
  demo-api
```

La imagen no trae Mongo adentro ni un `.env` horneado — `MONGO_URI`/`DB_NAME`
se pasan como variables de entorno al correr el contenedor, igual que corriendo
`run.sh` directo. Si Mongo corre en el host (no en un contenedor), usa
`host.docker.internal` como en el ejemplo; si corre en otro contenedor o en un
servicio externo (Atlas, un Mongo en ECS, etc.), pasa esa URI en su lugar.

El despliegue a AWS (ECS vía Terraform) es responsabilidad de otro bloque —
esta imagen es el único contrato: build, y correr con esas dos env vars.

## Endpoints

| Método | Ruta                  | Descripción                                             |
|--------|-----------------------|----------------------------------------------------------|
| GET    | `/invoices`           | Lista todas las facturas                                  |
| GET    | `/invoices/{id}`      | Detalle de una factura (404 si no existe)                 |
| GET    | `/health/consistency` | Semáforo de la demo: 200 si consistente, 409 si no         |
| POST   | `/admin/reset`        | Restaura la colección al seed limpio (idempotente)         |

### `GET /health/consistency`

```json
// 200
{ "consistent": true, "checked": 30, "violations": [] }
```

```json
// 409
{
  "consistent": false,
  "checked": 30,
  "violations": [
    {
      "invoice_id": "INV-1042",
      "rule": "total_mismatch",
      "expected": 130000,
      "found": 45000,
      "detail": "sum of line_items[].subtotal is 130000, but total is 45000"
    }
  ]
}
```

## Invariantes de negocio validadas

1. `total == suma(line_items[].subtotal)` → regla `total_mismatch`.
2. Cada `line_item` cumple `subtotal == qty * unit_price` → regla
   `line_item_subtotal_mismatch`.
3. Una factura `issued` o `paid` no puede tener `audit_log` vacío → regla
   `missing_audit_log`.

## Nota de integración para el Bloque 5 (flujo de agentes)

El flujo de agentes debe apuntar a la base **`demo_billing`**, colección
**`invoices`**, en la misma instancia de Mongo configurada acá vía
`MONGO_URI`. Cualquier modificación directa sobre esa colección (draft,
issued, paid, line_items, total, audit_log) se refleja de inmediato en
`GET /health/consistency` sin necesidad de reiniciar esta API.

Antes de correr la demo una segunda vez, llamar a `POST /admin/reset` para
volver a datos limpios — si no, la segunda corrida arranca desde datos ya
corrompidos por la corrida anterior.

## Decisiones tomadas

- Estructura en `app/` (en vez de un único `main.py`) para separar conexión
  a Mongo, invariantes y endpoints.
- El seed inicial no se ejecuta desde `run.sh` en bash; el propio FastAPI
  siembra en su evento de `startup` si la colección está vacía, para evitar
  duplicar lógica de conexión a Mongo en shell.
- El spec solo da el formato exacto de `violation` para `total_mismatch`;
  para `line_item_subtotal_mismatch` y `missing_audit_log` se usó el mismo
  shape (`invoice_id`, `rule`, `expected`, `found`, `detail`), con
  `expected`/`found` como strings descriptivos cuando el chequeo no es
  numérico (caso `missing_audit_log`).
- Seed de 30 facturas con mezcla 10 `draft` / 10 `issued` / 10 `paid`, IDs
  `INV-1001`..`INV-1030`, montos en COP como enteros (sin decimales). Las
  primeras 12 (`INV-1001`..`INV-1012`) son las originales del bloque; las
  18 restantes (`INV-1013`..`INV-1030`) se generaron a partir de un
  catálogo fijo de 15 SKUs con precio unitario constante, para que el
  dataset se sienta como el catálogo real de una empresa en vez de precios
  inventados por factura.
