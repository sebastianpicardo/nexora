# Auditoría de riesgos — Fase 0

**Fecha:** 12 de noviembre de 2026  
**Base auditada:** commit `7e0fb47` (`origin/main`)  
**Alcance:** inteligencia de precios, matching de productos, arranque en frío, costo de IA, seguridad multi-tenant, integraciones y consistencia de producto.  
**Método:** ejecución real contra PostgreSQL efímero, análisis de código y revisión de rutas. No se usó la base de Supabase ni datos de clientes.

## 1. Resumen ejecutivo

La plataforma tiene una base funcional y el aislamiento por organización funciona en los flujos principales probados. Sin embargo, **todavía no está en condiciones de venderse a 150.000 CLP + IVA/mes** por seis motivos críticos: los backups permiten fuga entre clientes, el pago está en modo simulado en producción, las oportunidades pueden mostrar ahorros falsos, las integraciones simulan éxito, la demo inicial no genera ahorro y los backups no existen en la imagen de producción.

### Prioridad P0 — bloquea la venta

| ID | Hallazgo | Impacto | Evidencia |
|---|---|---|---|
| P0-01 | Cualquier owner/admin puede listar, descargar y restaurar backups globales de toda la plataforma. | Un cliente puede exfiltrar la base completa de todos los clientes o restaurar un estado anterior. | `src/api/routes/backup.py:29-80`; `src/services/backup_service.py:14-16,41-58` |
| P0-02 | `PAYMENT_PROVIDER=mock` en producción. | Cualquier owner/admin puede activar Pro o Enterprise sin pagar y se emite una factura ficticia. | `render.yaml:60-61`; `src/api/routes/billing.py:281-300` |
| P0-03 | Las oportunidades de ahorro usan precios fuera de la ventana y precios futuros, y aceptan una sola muestra. | Muestra ahorros que no existen y destruye la credibilidad del producto en la primera reunión. | `src/db/repositories/insights.py:71-102`; resultado real: COMB-1 con 900 % de sobreprecio y FIE-1 con precio futuro |
| P0-04 | Integraciones nativas simuladas se presentan como disponibles y devuelven éxito falso. | Un cliente cree que notificó a Slack, aprobó una compra o guardó en Drive cuando nada ocurrió. | `src/services/native_integrations_service.py:76-88,337-395`; `client/src/pages/ApprovalsPage.jsx:105` |
| P0-05 | La demo de onboarding no puede producir ahorro: crea un solo documento y tres ítems sin historial. | El objetivo de demostrar ahorro en la primera sesión no se cumple. | `src/api/routes/enterprise.py:716-780` |
| P0-06 | La imagen de producción no instala `pg_dump` ni `psql`, pero Enterprise ofrece backups. | El backup no funciona en Render y la promesa comercial es falsa. | `Dockerfile:17-30`; `src/services/backup_service.py:18-32,60-124` |

### Prioridad P1 — corregir antes de escalar

| ID | Hallazgo | Impacto |
|---|---|---|
| P1-01 | La auditoría principal exige el mismo proveedor, mientras las oportunidades comparan entre proveedores. | Dos definiciones distintas del mismo producto y falsos negativos en la auditoría. |
| P1-02 | El producto se identifica por SKU del proveedor o descripción exacta, sin catálogo canónico ni alias. | SKUs iguales de productos distintos se mezclan; el mismo producto con distinto texto no se compara. |
| P1-03 | El índice de precios de Analítica mezcla productos y cantidades. | El resultado real fue 385,56 (cambio de 285,56 %) sin significado económico. |
| P1-04 | El pronóstico proyecta compras únicas como recurrentes y calcula tendencia con ventanas desiguales. | TOR-1, con un solo mes, se proyectó en 100.000 CLP; INS-1 mostró 166,67 % de tendencia. |
| P1-05 | No existe registro de tokens ni costo de IA por organización; reprocesar no consume cuota. | Margen impredecible y posibilidad de gasto ilimitado con un solo usuario. |
| P1-06 | El documento completo y hasta 8 imágenes se envían al proveedor de IA sin control de retención ni consentimiento. | Bloqueo de compliance y de seguridad para clientes con precios confidenciales. |
| P1-07 | Rate limiting global de 120 req/min por IP, en memoria y confiando en `X-Forwarded-For`. | No protege costo de IA ni permite límites por organización o usuario. |
| P1-08 | `document_filename` siempre queda nulo en la cola de aprobaciones. | El aprobador no puede identificar el documento de origen. |
| P1-09 | La auto-aprobación solo mira confianza y excepciones, sin monto máximo. | En la prueba se habilitaron 301.000 CLP para aprobación automática. |
| P1-10 | Precios y planes no coinciden entre frontend, base de datos, README y objetivo comercial. | Riesgo de cobrar mal o prometer funciones inexistentes. |

### Prioridad P2 — ordenar y medir

- La auto-aprobación registra auditoría incluso cuando aprueba 0 ítems (`src/api/routes/insights.py:160-166`).
- La cola de aprobaciones aplica `LIMIT 300` antes de calcular totales (`src/db/repositories/insights.py:505`); los resúmenes se truncarán con volumen.
- Las oportunidades no tienen un índice funcional para `COALESCE(sku, normalized_description) + base_unit`; el rendimiento debe medirse con 10.000+ ítems.
- Existe una copia completa del backend dentro de `client/src/` (`api/`, `core/`, `db/`, `parsers/`, `schemas/`, `services/`, `main.py`, `worker.py`), sin uso aparente por el frontend. Es deuda técnica y riesgo de editar el archivo equivocado.
- La función `similarity()` existe en `src/parsers/normalization/descriptions.py:95`, pero no se usa para matching.
- README y manual quedan desalineados con el código actual y deberán regenerarse al cierre de las correcciones.

## 2. Ejecución real de Inteligencia

### 2.1 Entorno y datos

- PostgreSQL efímero levantado con `pgserver`.
- Esquema `database/schema.sql` y migraciones `002_saas.sql` a `008_alert_config.sql` aplicados sin error.
- `/health/ready` respondió `200` con `database: connected`.
- Dataset: 2 organizaciones, 3 proveedores, 23 ítems en CLP y casos borde: mismo producto entre proveedores, distinta unidad base, distinta moneda, ítem rechazado, precio base de 400 días, precio futuro, una sola muestra, pronóstico mensual y excepción crítica.
- Endpoints ejecutados con `httpx.ASGITransport` y override de autenticación: overview, opportunities, opportunities con 730 días, forecast, analytics, approvals, auto-approve y aislamiento entre organizaciones.

### 2.2 Lo que funcionó correctamente

- Aislamiento por organización: la organización B no vio proveedores ni oportunidades de la organización A (`org_b_has_org_a_supplier: false`).
- La organización B no pudo auto-aprobar un ítem de la organización A (`approved: 0`).
- Los ítems rechazados, con otra moneda o con otra unidad base no entraron en las comparaciones.
- La aprobación automática bloqueó el ítem con excepción crítica (`auto_approve_critical: approved: 0`).
- El matching por descripción normalizada exacta entre proveedores sí funcionó en oportunidades: “Papel bond carta” se comparó entre Proveedor Tres y Proveedor Uno.

### 2.3 Hallazgos confirmados

#### F-01 — Baseline sin ventana temporal ni corte contra el futuro (crítico)

`price_opportunities` filtra la fila actual por los últimos `days`, pero las laterales `hist` y `best` no tienen límite inferior ni superior de fecha (`src/db/repositories/insights.py:71-101`). Por eso la mediana incluye precios de cualquier antigüedad y precios posteriores a la compra.

Evidencia real:

- `COMB-1`, Proveedor Dos, 1.000 CLP contra mediana de 100 CLP tomada de un precio de 400 días: 900 % de sobreprecio y 90.000 CLP de ahorro potencial.
- `FIE-1`, Proveedor Dos, 1.000 CLP contra mediana de 500 CLP tomada de un precio futuro: 100 % de sobreprecio y 5.000 CLP de ahorro potencial.

Corrección propuesta: en `hist` y `best`, agregar `h.price_date >= (r.price_date - interval 'N days')` y `h.price_date <= r.price_date`; excluir el documento actual; parametrizar la ventana y agregar pruebas con precios antiguos y futuros.

#### F-02 — `min_history_samples` no se respeta (alto)

La configuración define `min_history_samples = 2` (`src/core/config.py:127`), pero la consulta usa `hist.samples >= 1` (`src/db/repositories/insights.py:102`). `MAD-1` apareció como oportunidad con una sola muestra previa y 5.000 CLP de ahorro.

Corrección propuesta: usar `hist.samples >= %s` con `settings.min_history_samples`, exponer el mínimo en la respuesta y no mostrar oportunidades sin historia suficiente.

#### F-03 — Nombre de documento nulo en aprobaciones (alto)

La consulta selecciona `d.original_filename` (`src/db/repositories/insights.py:490`), pero la respuesta lee `row.get("document_filename")` (`src/db/repositories/insights.py:532`). Los 8 ítems de la prueba devolvieron `document_filename: null`.

Corrección propuesta: aliasar en SQL (`d.original_filename AS document_filename`) o leer `original_filename`; agregar prueba de contrato.

#### F-04 — Índice de precios engañoso (alto)

`analytics_overview` calcula `AVG(normalized_unit_price)` por mes sin separar producto ni cantidad (`src/db/repositories/insights.py:327-339`) y luego divide el promedio del último mes por el del primero (`:425-431`). El resultado real fue `price_index: 385,56` y `price_change_pct: 285,56 %`, producto de una canasta distinta cada mes y de incluir el mes en curso parcial.

Corrección propuesta: construir un índice tipo Laspeyres con canasta fija y precios comparables por producto/unidad, o renombrar el indicador como “precio promedio de canasta” y no presentarlo como inflación. Excluir el mes en curso hasta que cierre o comparar contra el mismo período.

#### F-05 — Pronóstico sobre datos insuficientes y tendencia mal calculada (alto)

- Incluye productos con un solo mes de historia; `TOR-1` se proyectó en 100.000 CLP desde una compra única.
- `prev_three = quantities[-6:-3] if len(quantities) > 3 else quantities[:-3]` (`src/db/repositories/insights.py:257`) compara ventanas de distinto tamaño cuando hay 4 a 6 meses. `INS-1` mostró `trend_pct: 166,67`.
- No rellena meses sin compras con cero, por lo que la tendencia depende de meses no contiguos.
- Excluye el mes en curso (`:225-226`), decisión correcta para no proyectar datos parciales, pero no se comunica en la UI.

Corrección propuesta: exigir mínimo 3 meses con datos (ideal 6), construir una serie mensual continua con ceros, comparar ventanas del mismo largo y etiquetar baja confianza cuando no haya suficiente historia.

#### F-06 — Dos definiciones de producto distintas (alto)

- Oportunidades compara entre proveedores por `COALESCE(sku, normalized_description)` (`src/db/repositories/insights.py:63`).
- La auditoría principal usa `get_price_history`, que exige `supplier_id IS NOT DISTINCT FROM` (`src/db/repositories/items.py:234`), misma `base_unit`, misma moneda y SKU o descripción exacta.

En la prueba, el histórico de cemento solo devolvió los dos precios del Proveedor Uno; no incluyó el precio del Proveedor Dos. El mismo ítem puede aparecer como oportunidad en una pantalla y no existir en la auditoría.

Corrección propuesta: una sola resolución de producto compartida por ambos flujos; definir explícitamente si la auditoría compara contra el mismo proveedor o contra el mercado y documentarlo en la UI.

#### F-07 — Identidad de producto frágil (alto, estructural)

`COALESCE(i.sku, i.normalized_description)` hace que el SKU tenga prioridad. El SKU suele ser propio de cada proveedor: dos proveedores pueden usar el mismo código para productos distintos, y el mismo producto puede tener códigos distintos. Además, la descripción se compara de forma exacta: “cemento gris 25 kg” y “cemento 25 kg gris” no coinciden, aunque `similarity()` esté disponible.

Corrección propuesta: catálogo canónico por organización (`canonical_products`) con alias por proveedor (`product_aliases`), matching conservador con revisión humana y nunca comparar por SKU entre proveedores sin alias explícito.

#### F-08 — Auto-aprobación sin tope de monto (alto)

La elegibilidad solo exige `confidence >= threshold` y cero excepciones de alta severidad (`src/db/repositories/insights.py:522-523`). La actualización no considera monto (`:572-585`). En la prueba se habilitaron 7 ítems por 301.000 CLP, incluido COMB-1 por 100.000 CLP y TOR-1 por 100.000 CLP.

Corrección propuesta: tope por monto, por proveedor y por período; doble aprobación sobre un umbral; registrar quién aprobó y con qué regla.

#### F-09 — Rendimiento no medido (riesgo P2)

La lateral calcula mediana y mínimo para cada fila y compara por una expresión sin índice funcional. No se midió con volumen; debe probarse con 10.000 a 100.000 ítems antes de prometer análisis en tiempo real.

## 3. Matching de productos entre proveedores

### 3.1 Situación actual

- Normalización de texto y abreviaturas en `src/parsers/normalization/descriptions.py:55-101`.
- Matching por igualdad exacta de `COALESCE(sku, normalized_description)` y unidad base.
- No hay catálogo canónico, alias, marca, formato ni conversión de presentaciones.
- La unidad distinta se excluye correctamente (caso guantes: caja contra unidad), pero eso también puede ocultar el mismo producto vendido en otra presentación.
- La moneda distinta se excluye correctamente (caso USD contra CLP), sin conversión.

### 3.2 Riesgo comercial

El ahorro se calcula contra un “mejor precio” que puede corresponder a otro producto si dos proveedores comparten SKU. En la dirección opuesta, el ahorro real puede no detectarse si el mismo producto se describe con otro orden de palabras. Para vender el producto como auditoría de compras, el catálogo canónico es requisito de Fase 2, no una mejora opcional.

### 3.3 Corrección propuesta

1. Crear `canonical_products` y `product_aliases` con `organization_id`.
2. Resolver aliases por proveedor, marca y presentación; guardar nivel de confianza del match.
3. Comparar solo con unidad convertida y moneda equivalente.
4. Mostrar “producto comparable” y permitir que el usuario corrija el match.
5. No calcular ahorro entre productos con match no confirmado.

## 4. Arranque en frío

`POST /api/enterprise/onboarding/demo` crea un único documento con tres ítems (`src/api/routes/enterprise.py:716-780`). Las oportunidades excluyen el mismo documento (`h.document_id <> r.document_id`) y el pronóstico excluye el mes en curso (`src/db/repositories/insights.py:225-226`). Por construcción, la demo:

- no genera oportunidades de ahorro;
- no genera pronóstico;
- solo muestra un dashboard con gasto y una excepción.

El banner de bienvenida es una animación de storytelling, no un resultado real. Para cumplir la promesa comercial se necesita una carga histórica guiada: 6 a 12 meses de documentos del mismo conjunto de productos, o un dataset demo con dos o más períodos y productos repetidos.

Corrección propuesta:

1. Demo con 12 meses, 10 productos y 3 proveedores, mostrando un ahorro conservador y trazable.
2. Importación masiva de carpeta ZIP o carga histórica asistida.
3. Checklist “sube tu primer mes” y “sube el segundo mes” con progreso.
4. Nunca mostrar ahorro si no hay al menos dos compras comparables.

## 5. Costo y uso de IA

### 5.1 Situación actual

- No existe tabla de uso de IA por documento, organización, proveedor o modelo.
- Solo OpenAI registra tokens en logs (`src/parsers/llm/openai_provider.py:70-75`); Gemini y Anthropic no registran uso.
- Se envían hasta 60.000 caracteres y 8 imágenes por documento (`src/core/config.py:119-120`; `src/parsers/llm/openai_provider.py:27-36`).
- Cada proveedor tiene reintentos con backoff; un fallo transitorio puede multiplicar llamadas y costo.
- La cuota de documentos se controla en la ingesta (`src/api/routes/documents.py:109-113`), pero `reprocess` no vuelve a consumir cuota (`:300-325`).
- El asistente no tiene cuota de IA ni límite por organización; cualquier rol autenticado puede invocarlo (`src/api/routes/assistant.py:25`).
- El único límite transversal es el rate limit global de 120 req/min.

### 5.2 Riesgo

No es posible saber el costo real por cliente ni fijar un precio con margen. Un usuario puede reprocesar documentos o usar el asistente sin un tope económico. A 150.000 CLP/mes, un cliente con documentos extensos y reprocesos puede consumir el margen completo.

### 5.3 Corrección propuesta

1. Migración `ai_usage` con `organization_id`, `document_id`, `provider`, `model`, `input_tokens`, `output_tokens`, `images`, `estimated_cost_usd`, `created_at`.
2. Registrar uso en los tres proveedores y en el asistente.
3. Cuota mensual de IA por plan y alerta al 80 %.
4. Que `reprocess` consuma cuota o tenga un límite explícito.
5. Panel de costo por organización para `super_admin`.
6. Rate limit específico para ingesta, reproceso y asistente.

## 6. Seguridad, multi-tenant y roles

### 6.1 Backups globales (crítico)

`backup.py` exige owner/admin, pero no valida organización ni rol global. `backup_service` usa un directorio global y `DATABASE_URL` completa. Cualquier owner/admin puede:

- listar todos los backups;
- descargar el dump completo con datos de todas las organizaciones;
- restaurar un backup y sobrescribir el estado global.

Corrección propuesta: mover backups a `super_admin`; si se ofrece backup por cliente, exportar solo su organización con un proceso aislado y cifrado. Nunca exponer un dump global a un rol de organización.

### 6.2 Pago simulado en producción (crítico)

`render.yaml:60-61` define `PAYMENT_PROVIDER=mock`. Con eso, `change-plan` omite el bloqueo de planes pagados (`src/api/routes/billing.py:281`) y crea una factura ficticia (`:295-300`). Cualquier owner/admin puede activar Enterprise gratis.

Corrección propuesta: eliminar `mock` del entorno productivo, fallar al arrancar si `APP_ENV=production` y el proveedor es mock, y exigir webhook firmado para activar planes pagados.

### 6.3 Rate limiting

`RateLimitMiddleware` es global, en memoria, por IP y toma el primer valor de `X-Forwarded-For` (`src/api/deps.py:94-135`). No distingue usuario, organización ni ruta. No protege el costo de IA y se reinicia con cada instancia.

Corrección propuesta: límites por organización y usuario en ingesta, reproceso, asistente y exportaciones; almacenamiento compartido cuando haya más de una instancia; no confiar en headers no verificados.

### 6.4 Datos enviados a IA

La extracción envía el texto completo y hasta 8 imágenes a un tercero. No hay aviso al cliente, opción de retención cero, redacción de datos sensibles ni registro de qué se envió. Para empresas chilenas con precios de proveedores y datos comerciales, esto debe resolverse antes de la venta.

Corrección propuesta: política de tratamiento de datos, proveedor con retención cero, opción de desactivar imágenes, minimización de texto y registro de consentimiento por organización.

### 6.5 Secretos

- No se encontraron claves de proveedores de IA en el bundle del frontend; solo `VITE_API_URL` y la site key pública de reCAPTCHA.
- Los secretos de webhooks e integraciones se guardan en la base sin cifrado de aplicación (`src/db/repositories/enterprise.py:786-790` y `:626-630`). Depende del cifrado en reposo del proveedor.
- La `service_role` de Supabase debe permanecer solo en el backend; una fuga permitiría saltar RLS.

Corrección propuesta: cifrar secretos de integración con una clave gestionada, rotarlos y no devolverlos en las respuestas de listado.

### 6.6 Roles y aislamiento

- Los flujos probados de oportunidades, aprobaciones y auto-aprobación respetaron `org_id`.
- El asistente acepta cualquier rol, incluido `viewer`.
- No se probaron todas las rutas con todos los roles en esta fase; se requiere una matriz automatizada.

Corrección propuesta: matriz de permisos por ruta y prueba de aislamiento para cada repositorio que recibe `org_id`.

## 7. Inventario real de integraciones

Todas se listan como `available: true`, `status: Disponible` y acciones `enabled: true` (`src/services/native_integrations_service.py:76-122`).

| Integración | Qué hace realmente | Etiqueta correcta |
|---|---|---|
| ChileCompra | Devuelve listas estáticas de ferretería; no consulta la API de ChileCompra. | Referencia / Beta |
| SII | Valida el formato del RUT; no consulta el SII. | Validación local / Próximamente |
| ERP | Devuelve nombres de archivos CSV; no genera ni envía archivos. | Exportación manual / Beta |
| Slack | Devuelve `enviado: true` sin enviar; “Aprobar compra” devuelve `estado: aprobado` sin cambiar la aprobación. | Próximamente |
| Webhook | Devuelve un payload para copiar; no hace POST. | Próximamente |
| Google Workspace | Devuelve `guardado: true` sin guardar; SSO solo tiene configuración, no aplicación de dominio. | Próximamente |

Además, la UI de aprobaciones muestra “Notificada en Slack” después de llamar al endpoint simulado (`client/src/pages/ApprovalsPage.jsx:100-105`). La página de integraciones dice que no se necesitan claves ni APIs (`client/src/pages/NativeIntegrationsPage.jsx:800-801`), aunque algunas notas aclaran que son referencias estimadas.

Existe un servicio de notificaciones real para email, Slack, webhook y WhatsApp cuando hay canal configurado (`src/services/notification_service.py`). Ese servicio no debe confundirse con los botones simulados de integraciones nativas.

Corrección propuesta: deshabilitar acciones no implementadas, etiquetarlas “Beta” o “Próximamente” y nunca devolver éxito si no hubo efecto verificable. Si se mantiene el modo referencia, decirlo en el botón y en el resultado.

## 8. Inconsistencias de producto y documentación

| Tema | Frontend | Base de datos / código | Objetivo |
|---|---|---|---|
| Documentos Free | Hasta 50 por mes | 25 (`database/migrations/002_saas.sql:37`) | Definir uno |
| Precio Pro | 49 USD/mes | 49 USD/mes | Definir moneda y equivalente CLP |
| Precio Enterprise | 149 USD/mes | 199 USD/mes | Definir uno |
| Precio objetivo | No aparece | No aparece | 150.000 CLP + IVA/mes |
| Prueba gratuita | 14 días sin tarjeta | No hay creación de trial en el backend | Implementar o eliminar |
| Historial | 6 meses en el plan Pro | Analytics permite 24 meses; oportunidades 730 días; pronóstico 12 meses | Alinear límites por plan |
| Facturación | Checkout visible | Stripe, MercadoPago, Flow y mock existen | README dice que no hay cobro automático |
| Multi-sucursal | Enterprise “Múltiples sucursales” | No hay modelo de sucursales | Implementar o quitar |
| White-label | Enterprise disponible | Branding por organización existe | Verificar alcance real |
| SSO Google Workspace | Enterprise disponible | Solo configuración `sso_enabled`/`sso_domain` | Implementar aplicación o marcar próximamente |

También hay que alinear el README: declara que no hay cobro automático (`README.md:371`) y que las notificaciones de cuota no se envían (`:372`), mientras el código ya tiene checkout y servicio de notificaciones. El manual PDF de 24 páginas debe regenerarse después de las correcciones de Fase 1 y Fase 2.

## 9. Plan de corrección recomendado

### Fase 1 — Confiabilidad y seguridad

1. Corregir baseline de oportunidades, mínimo de muestras y nombre de documento.
2. Reemplazar índice de precios y corregir pronóstico.
3. Unificar definición de producto entre oportunidades y auditoría.
4. Bloquear backups globales y eliminar `mock` de producción.
5. Instalar `pg_dump`/`psql` o deshabilitar backups en producción.
6. Crear `ai_usage`, cuotas de IA y rate limits específicos.
7. Pruebas de aislamiento multi-tenant y matriz de roles.

### Fase 2 — Valor comercial

1. Catálogo canónico y aliases.
2. Carga histórica masiva y demo con 12 meses.
3. Motor de ahorro conservador con evidencia y rango.
4. Informe PDF, link compartible y seguimiento de ahorro.
5. Integraciones reales o etiquetadas.

### Fase 3 — Cierre

1. Pruebas de casos borde y Playwright.
2. Manual actualizado y `docs/CHECKLIST_REDEPLOY.md`.
3. Verificación en Render con Supabase real.

## 10. Limitaciones de esta auditoría

- La ejecución se hizo contra PostgreSQL efímero, no contra Supabase.
- El script de auditoría fue temporal y no se incorporó al repositorio; las pruebas reproducibles se crearán en Fase 1.
- No se hizo prueba de carga ni de penetración formal.
- No se probaron todos los roles en todas las rutas; eso queda para la matriz automatizada.
- No se validaron pagos reales, envíos reales de correo, Slack ni proveedores externos.
- Las cifras de ahorro citadas provienen del dataset de prueba y demuestran el comportamiento del motor, no el ahorro de un cliente real.

## 11. Evidencia de la ejecución

Resultados principales obtenidos:

- `/health/ready`: `200`, `database: connected`.
- Oportunidades con 90 días: 8 oportunidades, 169.000 CLP de ahorro potencial.
- COMB-1: 900 % de sobreprecio por baseline de 400 días.
- FIE-1: 100 % de sobreprecio por precio futuro.
- MAD-1: oportunidad con 1 sola muestra.
- Analítica: `price_index 385,56`, `price_change_pct 285,56 %`.
- Pronóstico: TOR-1 con 1 mes proyectado en 100.000 CLP; INS-1 con tendencia de 166,67 %.
- Aprobaciones: 8 pendientes, 7 auto-elegibles por 301.000 CLP; todos los `document_filename` nulos.
- Auto-aprobación de ítem crítico: `approved: 0`.
- Auto-aprobación cruzada entre organizaciones: `approved: 0`.
- Organización B no vio proveedores de organización A.
- `get_price_history` de cemento devolvió solo los precios del Proveedor Uno, no los del Proveedor Dos.
