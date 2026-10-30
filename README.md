# NEXORA

NEXORA es un Micro-SaaS B2B para distribuidores industriales que convierte cotizaciones, facturas y listas de precios en un histórico de compras normalizado. Detecta alzas de precio contra la mediana histórica, valida unidades y totales, y envía los casos dudosos a una bandeja de revisión humana.

## Funcionalidades

- Ingesta de PDF, Excel, CSV, TXT e imágenes.
- Extracción estructurada con LLM y esquema Pydantic validado.
- Normalización de unidades físicas (kg, g, L, m³, m², etc.) y empaques (`caja x 12 kg`).
- Normalización de moneda, fechas y descripciones de productos.
- Precio unitario normalizado por SKU, proveedor y fecha.
- Detección de alzas contra mediana histórica configurable.
- Validación de totales de línea y confianza de extracción.
- Bandeja Human-in-the-Loop para aprobar, corregir o rechazar excepciones.
- Multitenant por organización con aislamiento por `org_id`.
- Login con Google y sesión JWT en cookie HttpOnly.
- Roles `super_admin`, `owner`, `admin`, `analyst`, `user`, `auditor` y `viewer`.
- Equipo con invitaciones, cambio de rol y desactivación de miembros.
- Planes Free, Pro y Enterprise con cuota mensual de documentos y alertas de consumo.
- Panel global de super administración con organizaciones, consumo y MRR.
- Perfil de usuario con cargo, teléfono, zona horaria y preferencias de notificación.
- Dashboard con actividad, gasto del mes, evolución mensual, cuota y pendientes.
- Exportaciones de excepciones y precios en Excel y PDF.
- Procesamiento en background o worker independiente.

## Arquitectura

```text
React + Vite
     |
     | HTTP / cookie JWT
     v
FastAPI ──────────> Supabase Postgres
   |  \                  |
   |   \                 └─ RLS + org_id
   |    \
   |     └──────────> Supabase Storage / disco local
   |
   ├───────────────> OpenAI | Anthropic | Gemini
   |
   └───────────────> Worker de documentos
```

El frontend compilado se sirve desde FastAPI en producción. En desarrollo, Vite corre en `5173` y hace proxy de `/api` y `/health` a FastAPI en `8000`.

## Estructura

```text
NEXORA/
├── database/
│   ├── migrations/
│   │   └── 002_saas.sql
│   ├── schema.sql
│   └── seed.sql
├── scripts/
│   ├── init_db.py
│   └── process_pending.py
├── src/
│   ├── api/
│   │   ├── deps.py
│   │   ├── router.py
│   │   └── routes/
│   ├── core/
│   ├── db/
│   │   └── repositories/
│   ├── parsers/
│   │   ├── extractors/
│   │   ├── llm/
│   │   └── normalization/
│   ├── schemas/
│   ├── services/
│   ├── main.py
│   └── worker.py
├── client/
│   ├── src/
│   │   ├── components/
│   │   ├── context/
│   │   ├── lib/
│   │   └── pages/
│   └── vite.config.js
├── tests/
├── Dockerfile
├── render.yaml
└── requirements.txt
```

## Requisitos

- Python 3.12
- Node.js 20.19+ o 22.12+
- Proyecto de Supabase con Postgres y Storage
- Credenciales OAuth 2.0 de Google
- API key de OpenAI, Anthropic o Gemini

En Windows, Python puede instalarse con:

```powershell
winget install -e --id Python.Python.3.12
```

Si `python` sigue abriendo Microsoft Store, desactiva el alias en **Configuración → Aplicaciones → Configuración avanzada de aplicaciones → Alias de ejecución de aplicaciones**, o usa la ruta completa:

```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" -m venv .venv
```

## Configuración local

### 1. Dependencias

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
```

En macOS/Linux:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
```

### 2. Supabase

1. Crea un proyecto en Supabase.
2. Abre **SQL Editor** y ejecuta el contenido de `database/schema.sql`.
3. Crea un bucket privado llamado `nexora-documents`.
4. Obtén la cadena de conexión desde **Project Settings → Database → Connection string**.
5. Para despliegues usa el pooler en el puerto `6543` y añade `?sslmode=require`.
6. Copia `SUPABASE_URL` y `SUPABASE_SERVICE_ROLE_KEY` solo al backend.

El esquema crea `organizations`, `users`, `suppliers`, `documents_log`, `items_history`, `exceptions_log`, `plans`, `subscriptions` y `team_invitations`, con índices, triggers de `updated_at` y RLS. Las tablas tienen RLS activado y permisos revocados para `anon` y `authenticated`; el backend se conecta con el rol de Postgres.

Para actualizar una base existente creada antes del módulo SaaS, ejecuta `database/migrations/002_saas.sql`. La migración agrega perfiles, roles extendidos, planes, suscripciones e invitaciones. El código nuevo de creación de usuarios requiere esa migración antes de desplegarse.

### 3. Google OAuth

En Google Cloud Console:

1. Crea un **OAuth client ID** de tipo **Web application**.
2. Añade el origen autorizado `http://localhost:5173`.
3. Añade el redirect URI `http://localhost:8000/api/auth/google/callback`.
4. Para producción añade el dominio real y `https://TU_DOMINIO/api/auth/google/callback`.

### 4. Variables de entorno

```powershell
Copy-Item .env.example .env
```

Completa como mínimo:

| Variable | Descripción |
| --- | --- |
| `DATABASE_URL` | URI de Postgres de Supabase |
| `JWT_SECRET` | Secreto largo y aleatorio para firmar JWT |
| `SESSION_SECRET` | Secreto largo para la sesión de Authlib |
| `GOOGLE_CLIENT_ID` | Client ID de Google |
| `GOOGLE_CLIENT_SECRET` | Client Secret de Google |
| `GOOGLE_REDIRECT_URI` | Callback exacto registrado en Google |
| `SUPER_ADMIN_EMAILS` | Emails separados por coma que reciben rol global `super_admin` |
| `OPENAI_API_KEY` | API key del proveedor LLM seleccionado |
| `FRONTEND_URL` | URL del cliente para redirecciones OAuth |
| `CORS_ORIGINS` | Orígenes permitidos, separados por coma |

`DEFAULT_CURRENCY`, `DEFAULT_PRICE_SPIKE_THRESHOLD_PCT` y `MIN_EXTRACTION_CONFIDENCE` se usan al crear una organización nueva. Después puedes ajustarlos desde `PATCH /api/organizations/current`.

`SUPER_ADMIN_EMAILS` se aplica al iniciar sesión: si el email coincide, el usuario recibe el rol global `super_admin`. Después de cambiar esta variable, el usuario debe volver a iniciar sesión.

Genera secretos con:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Para desarrollo con almacenamiento local:

```env
STORAGE_BACKEND=local
LOCAL_UPLOAD_DIR=./uploads
```

Para producción se recomienda:

```env
STORAGE_BACKEND=supabase
COOKIE_SECURE=true
APP_ENV=production
```

### 5. Base de datos

```powershell
python scripts/init_db.py
```

Ejecuta este script una vez por proyecto o después de cambiar `schema.sql`. Es idempotente porque el esquema usa `IF NOT EXISTS` y recrea triggers con `DROP TRIGGER IF EXISTS`. Si tu proyecto de Supabase rechaza DDL a través del pooler, usa temporalmente la conexión directa del puerto `5432` para inicializar y vuelve al pooler `6543` para la aplicación.

### 6. Backend

```powershell
python scripts/dev_server.py
```

En macOS/Linux también puedes usar `uvicorn src.main:app --reload --port 8000`. En Windows usa siempre `scripts/dev_server.py`: fuerza un `SelectorEventLoop`, necesario porque `psycopg` async no soporta el `ProactorEventLoop` por defecto.

- API: `http://localhost:8000`
- Documentación: `http://localhost:8000/docs`
- Health: `http://localhost:8000/health`

### 7. Frontend

```powershell
cd client
npm ci
npm run dev
```

Abre `http://localhost:5173`. El primer login con Google crea automáticamente la organización y el usuario `owner`.

### 8. Worker opcional

Con `PROCESS_IN_BACKGROUND=true`, la API procesa el documento al subirlo mediante `BackgroundTasks`. El worker queda disponible para documentos que hayan quedado en cola o bloqueados en `processing`:

```powershell
python -m src.worker
```

El worker configura automáticamente un loop compatible en Windows.

Para procesar un solo documento en cola:

```powershell
python -m src.worker --once
```

También puedes usar el script:

```powershell
python scripts/process_pending.py --once
```

## Flujo de uso

1. Inicia sesión con Google.
2. Sube una cotización, factura o lista de precios.
3. NEXORA extrae las líneas con el proveedor LLM configurado.
4. Normaliza descripción, unidad, cantidad, moneda y precio unitario.
5. Compara el precio con la mediana histórica del mismo ítem, proveedor, moneda y unidad base.
6. Genera excepciones para baja confianza, unidades no reconocidas, totales inconsistentes o alzas relevantes.
7. Revisa la bandeja de excepciones y aprueba, corrige o rechaza.
8. Consulta el histórico normalizado y el dashboard.

## Endpoints principales

| Método | Ruta | Descripción |
| --- | --- | --- |
| `GET` | `/health` | Liveness del servicio, sin consultar la base |
| `GET` | `/health/ready` | Readiness del servicio y conexión a la base |
| `GET` | `/api/auth/google` | Inicia el flujo OAuth de Google |
| `GET` | `/api/auth/google/callback` | Callback OAuth y creación de sesión |
| `GET` | `/api/auth/me` | Usuario y organización actuales |
| `POST` | `/api/auth/logout` | Elimina la cookie de sesión |
| `GET` | `/api/organizations/current` | Organización actual |
| `PATCH` | `/api/organizations/current` | Ajustes de umbral y confianza |
| `GET` | `/api/suppliers` | Lista proveedores |
| `POST` | `/api/suppliers` | Crea un proveedor |
| `POST` | `/api/documents/ingest` | Sube y encola un documento |
| `GET` | `/api/documents` | Lista documentos con paginación |
| `GET` | `/api/documents/{id}` | Detalle de documento |
| `POST` | `/api/documents/{id}/reprocess` | Reencola un documento |
| `GET` | `/api/items` | Histórico de precios con filtros |
| `GET` | `/api/items/{id}` | Detalle de un ítem |
| `GET` | `/api/exceptions` | Bandeja de excepciones |
| `POST` | `/api/exceptions/{id}/resolve` | Resuelve una excepción |
| `GET` | `/api/dashboard/summary` | Resumen del dashboard, evolución mensual y cuota |
| `GET` | `/api/profile` | Perfil del usuario autenticado |
| `PATCH` | `/api/profile` | Actualiza perfil y preferencias |
| `GET` | `/api/team` | Miembros e invitaciones de la organización |
| `POST` | `/api/team/invitations` | Genera una invitación |
| `POST` | `/api/team/invitations/accept` | Acepta una invitación pendiente |
| `DELETE` | `/api/team/invitations/{id}` | Revoca una invitación |
| `PATCH` | `/api/team/members/{id}` | Cambia rol o estado de un miembro |
| `GET` | `/api/billing/summary` | Plan, suscripción, cuota y planes disponibles |
| `POST` | `/api/billing/change-plan` | Cambia el plan de la organización |
| `GET` | `/api/admin/overview` | Métricas globales; requiere `super_admin` |
| `GET` | `/api/exports/exceptions` | Exporta excepciones en `xlsx` o `pdf` |
| `GET` | `/api/exports/items` | Exporta precios auditados en `xlsx` o `pdf` |

Los endpoints de negocio requieren la cookie `nexora_token`. La lectura está disponible para todos los roles activos; la ingesta y revisión requieren `owner`, `admin`, `analyst` o `user`; la gestión de equipo, facturación y ajustes requiere `owner` o `admin`; `super_admin` accede además al panel global. `viewer` y `auditor` son roles de solo lectura.

## Pruebas y calidad

```powershell
pytest -q
ruff check .
```

Los tests no requieren conexión a Supabase. La mayoría usa `APP_ENV=test` y mockea el pool; las pruebas de integración levantan un PostgreSQL efímero con `pgserver`, aplican `schema.sql` y validan ingesta, normalización, excepciones, resolución HITL, dashboard, reproceso, billing, invitaciones, perfiles, RBAC, panel global y exportaciones. La suite cubre seguridad JWT, health, unidades, moneda, descripciones, pricing, esquema de extracción, pipeline, imágenes y storage.

Para el frontend:

```powershell
cd client
npm run build
```

Si `npm install` falla con `Cannot read properties of null (reading 'edgesOut')`, usa `npm ci` o actualiza npm a 11+.

## Docker

```powershell
docker build -t nexora .
docker run --rm -p 8000:8000 --env-file .env nexora
```

El Dockerfile compila el cliente con Node 24 y copia `client/dist` a la imagen final de Python 3.12. FastAPI sirve el frontend en `/`.

Para almacenamiento persistente en producción usa `STORAGE_BACKEND=supabase`. Si usas `local`, el sistema de archivos de Render es efímero.

## Despliegue en Render

El archivo `render.yaml` define:

- `nexora-web`: servicio web Docker con health check en `/health`.
- `nexora-worker`: worker Docker con comando `python -m src.worker`.

Pasos:

1. Sube el repositorio a GitHub.
2. En Render, crea un **Blueprint** y apunta a `render.yaml`.
3. Completa las variables marcadas con `sync: false`:
   - `DATABASE_URL`
   - `JWT_SECRET`
   - `SESSION_SECRET`
   - `GOOGLE_CLIENT_ID`
   - `GOOGLE_CLIENT_SECRET`
   - `SUPER_ADMIN_EMAILS`
   - `GEMINI_API_KEY`
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_ROLE_KEY`
4. Confirma `FRONTEND_URL`, `CORS_ORIGINS` y `GOOGLE_REDIRECT_URI` con el dominio de Render.
5. Añade el redirect de producción en Google Cloud Console.
6. Despliega y verifica `/health` y `/health/ready`.

`/health` es liveness y no consulta Postgres, para que Render no retire el contenedor por una caída temporal de la base. `/health/ready` valida la conexión y devuelve `503` si Supabase no responde.

No Expongas `SUPABASE_SERVICE_ROLE_KEY`, `OPENAI_API_KEY`, `JWT_SECRET` ni `GOOGLE_CLIENT_SECRET` en el cliente.

## Seguridad

- Cookie JWT `HttpOnly`, `SameSite=Lax` y `Secure` en producción.
- `JWT_SECRET` debe tener al menos 32 caracteres en producción.
- Todas las consultas de negocio filtran por `org_id`.
- RLS activado en Supabase y permisos revocados para roles anónimos.
- Invitaciones con token aleatorio, expiración y visibilidad solo para administradores.
- Protección del propietario y del super administrador frente a cambios de otros administradores.
- Validación de extensión, tamaño y hash SHA-256 para evitar duplicados.
- Límite de páginas y caracteres enviados al LLM.
- Errores internos no exponen trazas al cliente.

## Limitaciones actuales

- El OCR depende de la calidad de la imagen; conviene subir PDFs con texto cuando sea posible.
- La detección de alzas usa mediana histórica por proveedor, moneda, unidad base y SKU/descripción; no sustituye una auditoría financiera.
- El frontend usa navegación por estado, sin router ni rutas profundas.
- Los cambios de plan son administrativos y todavía no hay cobro automático con una pasarela de pago.
- Las notificaciones de cuota y el resumen semanal guardan preferencias, pero el envío de correos aún no está implementado.
- El almacenamiento local no es persistente en plataformas efímeras; en producción usa Supabase Storage.
- El plan de Render debe permitir workers si se quiere procesamiento separado del web.
