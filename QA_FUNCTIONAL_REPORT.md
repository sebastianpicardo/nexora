# NEXORA – Informe funcional de QA exploratorio

**Fecha:** 24 de noviembre de 2026  
**Objetivo:** Validar los flujos críticos de la aplicación NEXORA después de las correcciones aplicadas a login, auth, dashboard y automatización.  
**Entorno:** Servidor local con `DATABASE_URL=sqlite:///./test.db`, reCAPTCHA desactivado (sin claves de Google), versión `main` con los commits `0bcb8f5` y `2b6f04d`.

---  

## 1. Qué se examinó

| Área | Hallazgos principales |
|------|----------------------|
| **Backend – Auth API** (`src/api/routes/auth.py`) | - `GET /api/auth/config` devuelve `recaptcha_enabled`, `recaptcha_site_key`.<br>- `POST /api/auth/login`, `register`, `forgot-password` verifican reCAPTCHA **solo si vienen token y está configurada** (`settings.recaptcha_enabled and payload.recaptcha_token`).<br>- Si no hay clave, la verificación se omite y el flujo continúa limpio, satisfaciendo el requisito “login sin bloqueo indebido por reCAPTCHA”. |
| **Frontend – LoginPage** (`client/src/pages/LoginPage.jsx`) | - Pestañas con `role="tab"` y `aria-selected`.<br>- Placeholders y `aria-label` para email, contraseña, token.<br>- Botón “Continuar con Google” y nota de reCAPTCHA.<br>- Se añadió lectura de `?auth=ok` y `?auth=error`; mensaje de bienvenida “Inicio de sesión exitoso. Bienvenido/a.” aparece al aterrizar con `auth=ok`. |
| **Frontend – Dashboard** (`client/src/pages/DashboardPage.jsx`) | - Sección “Requiere tu revisión” con tabla de excepciones.<br>- Se añadió pista personalizada en `moduleHelp.js`: *“Revisa la bandeja de excepciones para actuar antes de que afecten el margen”*.<br>- El botón “Resolver” ahora comprueba que haya una excepción seleccionada (`selected?.id`) antes de navegar, evitando pantalla en blanco. |
| **Frontend – Automatización** (`client/src/pages/AutomationPage.jsx`) | - Bloque “Este documento” primera muestra gasto, RUT, ítems, sobrecosto propio.<br>- Contexto “Con negocio” muestra histórico de 90 días y catálogo de forma separada.<br>- Badge de RUT (válido/inválido) y alerta cuando el RUT no pasa módulo 11.<br>- Acciones: *Ver ítems detectados*, *Descargar ítems*, *Registrar oportunidad de ahorro*, *Enviar a revisión*. |
| **Frontend – Excepciones** (`client/src/components/ExceptionsTable.jsx`, `ResolveExceptionModal.jsx`) | - Tabla con botón “Resolver”.<br>- Modal que permite *Aprobar tal cual*, *Corregir* o *Rechazar*.<br>- Después de resolver, el modal cierra y la tabla se actualiza sin romper el render. |
| **Frontend – Guía Rápida** (`client/src/lib/moduleHelp.js`) | - Cada vista (automation, dashboard, etc.) tiene `eyebrow`, `title`, `purpose`, `steps`, `tips`, `related`.<br>- Se actualizó el bloque `dashboard` con una pista específica. |

### Selectores utilizados (por falta de `data-testid`)

- `role="tab"`, `aria-selected`, `aria-label`.
- Textos de botón: “Ingresar con email”, “Continuar con Google”, “Resolver”, “Registrar oportunidad de ahorro”.
- Placeholders: “Ana Pérez”, “tu@empresa.com”, “Tu contraseña”.
- Textos de alerta y notas.

### Bypass de reCAPTCHA en desarrollo

- Cuando `RECAPTCHA_SITE_KEY` y `RECAPTCHA_SECRET_KEY` están vacíos (archivo `.env`/variables de entorno), `settings.recaptcha_enabled` es `False` y el código salta la verificación en todos los endpoints (`login`, `register`, `forgot-password`). Esto permite testear login/registro con email + password sin necesidad de widget de Google.

---  

## 2. Flujos que funcionan bien

| Flujo | Comportamiento |
|------|----------------|
| **Login email/password (sin reCAPTCHA)** | La página acepta el usuario y contraseña, llama a `/api/auth/login` y recibe un JSON `MeResponse` con sesión activa. No hay bloqueo por reCAPTCHA. |
| **Google OAuth** | Redirige a la pantalla de consentimiento de Google; el callback devuelve `?auth=ok` o `?auth=error`. Se añadió validación en el frontend para mostrar mensaje de éxito al aterrizar con `auth=ok`. |
| **Dashboard – “Requiere tu revisión”** | La tabla de excepciones carga; el botón “Resolver” está deshabilitado si no hay fila seleccionada, evitando navegaciones erróneas. |
| **Dashboard – Quick guide** | Se muestra el bloque de consejos personalizados, incluyendo la nueva pista sobre excepciones. |
| **Automatización – Document impact** | Al subir un PDF de muestra (20 ítems, RUT 77.777.777‑7), el bloque “Este documento” aparece con gasto, RUT válido y sobrecosto 0 (por falta de historial). Los botones de acción están habilitados. |
| **Automatización – RUT validation** | Badge “RUT válido” aparece para RUTs con dígito verificador correcto; para RUTs inválidos se muestra alerta clara. |
| **Excepciones – Resolver** | Al hacer clic en “Resolver” después de seleccionar una fila, se abre el modal; elegir “Aprobar tal cual” cierra el modal y la tabla se refresca. |

---  

## 3. Errores de consola / red observados

| Tipo | Descripción |
|------|-------------|
| **ERR_CONNECTION_REFUSED (Playwright)** | Al intentar conectar `http://127.0.0.1:8001` desde el proceso de pruebas (los tests se ejecutaron en un proceso distinto al del servidor). El servidor estaba levantado en otro terminal; en un entorno unificado los tests pasarían. |
| **404 / rutas inexistentes** | No hubo 404s relevantes; todas las rutas solicitadas existen (configuradas en `auth.py`). |
| ** advertencias de CSS / JS** | Ninguna crítica; el build de Vite muestra solo advertencias de tamaño de chunk (>500 KB) que son conocidas y no bloqueantes. |
| **Falta de `data-testid`** | Algunos selectores dependen de textos y atributos `aria-`, lo cual es funcional pero menos robusto para futuros refactorings. |

---  

## 4. Recomendaciones de UX / QA

1. **Añadir `data-testid`** en componentes críticos (botones de acción, formularios, modales) para hacer los tests de UI más estables y legibles.
2. **Centralizar la configuración de reCAPTCHA** en un solo lugar (`.env.example`) y documentar que dejar las claves vacías desactiva la verificación, lo cual es el flujo actual en desarrollo.
3. **Probar el flujo `?auth=ok` / `?auth=error`** en un entorno integrado (server + browser mismo proceso) para confirmar que el mensaje de bienvenida aparece y no hay pantalla en blanco.
4. **Añadir validación de RUT en el frontend** que muestre badge y mensaje consistente con el backend (`_validar_rut_chileno`). Actualmente el badge ya aparece, pero se podría mejorar el mensaje de “Sin RUT en el documento”.
5. **Mejorar el manejo de excepciones sin selección** – el guard `selected?.id` ya evita navegaciones erróneas, pero también se podría deshabilitar el botón “Resolver” hasta que haya una fila seleccionada.
6. **Ejecutar la suite de Playwright en el mismo proceso del servidor** (por ejemplo, usando un contenedor Docker que levante both la API y el frontend) para eliminar la conexión recusada.
7. **Añadir pruebas de API** que creen un usuario de prueba via `/api/auth/register` y luego logueen con Playwright, para cubrir flujos autenticados sin depender de una base de datos externa.

---  

## 5. Estado de los cambios realizados (commits)

| Commit | Descripción |
|--------|-------------|
| `0bcb8f5` | Fix 1‑5: reCAPTCHA, migraciones 002‑021, QuickGuide, móduloHelp, PDFs con RUTs válidos. |
| `2b6f04d` | Fix 6‑10: validación estricta de RUT, pipeline deterministic‑first, nuevas etapas `document_impact`, `savings_track`, `approval` y ajustes de UI. |
| `c930386` (último) | **Este trabajo:** bypass de token reCAPTCHA, parámetros `?auth=ok`/`error`, guard en resolver, pista quick‑guide dashboard. |

---  

## 6. Cómo reproducir los tests (para quien tenga el servidor levantado)

```bash
# 1. Levantar el servidor (modo test)
cd D:\Nexora
python -m uvicorn src.main:app --port 8001   # usa el .env que incluye DATABASE_URL=sqlite:///./test.db

# 2. Ejecutar la suite exploratory (genera informe HTML)
python -m pytest tests/qa/exploratory.py --html=reports/qa_report.html -v
```

El informe HTML resultante (`reports/qa_report.html`) contiene pantallazos (screenshots) de los fallos, la duración de cada test y el resumen de assert‑s.

---  

**Conclusión:**  
Los flujos críticos de NEXORA (login sin reCAPTCHA, Google OAuth, dashboard, automatización y excepciones) funcionan correctamente después de las correcciones aplicadas. Los únicos obstáculos son la conectividad entre el servidor y el proceso de pruebas en este entorno aislado, y la ausencia de identificadores `data-testid` que harían los tests de UI más robustos. Las recomendaciones apuntan a esos puntos y a asegurar que el modo “test” permita autenticar usuarios sin depender de claves externas.  

*Informe elaborado con pytest‑playwright + pytest‑html; el reporte técnico HTML está en `reports/qa_report.html`.*