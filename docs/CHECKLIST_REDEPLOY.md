# Checklist de redeploy

## 1. Aplicar SQL en Supabase
Ejecutar **un solo archivo** en Supabase SQL Editor, como owner del esquema:

`database/supabase_apply_pending.sql`

Incluye las migraciones `007` a `014` en orden y es idempotente. Al final devuelve una fila de verificación con todas las columnas en `true`. El único cambio de datos es el precio del plan `enterprise` a `150000 CLP/mes`.

## 2. Variables de entorno en Render

### Obligatorias
| Variable | Valor para producción | Nota |
| --- | --- | --- |
| `APP_ENV` | `production` | Activa validaciones estrictas. |
| `FRONTEND_URL` | `https://nexora-web-g9td.onrender.com` | Cámbialo si usas dominio propio. |
| `CORS_ORIGINS` | `https://nexora-web-g9td.onrender.com` | Mismo origen que `FRONTEND_URL`. |
| `DATABASE_URL` | `postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres?sslmode=require` | Usar connection string del pooler de Supabase. |
| `JWT_SECRET` | secreto aleatorio de 64+ caracteres | Obligatorio, mínimo 32. |
| `SESSION_SECRET` | secreto aleatorio de 64+ caracteres | Obligatorio, mínimo 32. |
| `SECRET_ENCRYPTION_KEY` | secreto aleatorio de 64+ caracteres | Cifra secretos de integraciones en reposo. No rotar sin re-cifrar los valores existentes. |
| `COOKIE_SECURE` | `true` | Obligatorio en producción. |
| `COOKIE_SAMESITE` | `lax` | Valor por defecto recomendado. |
| `PAYMENT_PROVIDER` | `stripe` | También `mercadopago` o `flow`. `mock` está prohibido en producción. |
| `PAYMENT_WEBHOOK_SECRET` | secreto aleatorio | Firma HMAC de webhooks no-Stripe. |
| `PAYMENT_SUCCESS_URL` | `https://nexora-web-g9td.onrender.com/?checkout=success` | Retorno después del pago. |
| `PAYMENT_CANCEL_URL` | `https://nexora-web-g9td.onrender.com/?checkout=cancel` | Retorno al cancelar. |
| `STORAGE_BACKEND` | `supabase` | Si es `local`, los archivos se pierden en cada redeploy. |
| `SUPABASE_URL` | `https://<ref>.supabase.co` | Project Settings > API. |
| `SUPABASE_SERVICE_ROLE_KEY` | `<service-role-key>` | Solo backend. Nunca en el cliente. |
| `SUPABASE_STORAGE_BUCKET` | `nexora-documents` | Crear el bucket en Supabase Storage. |

Generar secretos:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

### Google OAuth
| Variable | Valor |
| --- | --- |
| `GOOGLE_CLIENT_ID` | `<client-id>.apps.googleusercontent.com` |
| `GOOGLE_CLIENT_SECRET` | `<client-secret>` |
| `GOOGLE_REDIRECT_URI` | `https://nexora-web-g9td.onrender.com/api/auth/google/callback` |

Agregar exactamente esa redirect URI autorizada en Google Cloud Console.

### reCAPTCHA v3
| Variable | Valor |
| --- | --- |
| `RECAPTCHA_SITE_KEY` | `<site-key>` |
| `RECAPTCHA_SECRET_KEY` | `<secret-key>` |
| `RECAPTCHA_MIN_SCORE` | `0.5` |

El cliente obtiene la site key desde `/api/auth/config`; no se requiere `VITE_RECAPTCHA_SITE_KEY` si el frontend se sirve desde el backend.

### Correo transaccional (SMTP)
| Variable | Valor de ejemplo |
| --- | --- |
| `SMTP_HOST` | `smtp.gmail.com` o el host de tu proveedor |
| `SMTP_PORT` | `587` con STARTTLS; `465` con SSL |
| `SMTP_USER` | `tu-cuenta@dominio.com` |
| `SMTP_PASSWORD` | contraseña de aplicación o API key del proveedor |
| `SMTP_FROM` | `no-reply@tudominio.com` |
| `SMTP_FROM_NAME` | `NEXORA` |
| `SMTP_TLS` | `true` si usas el puerto `587` |
| `SMTP_SSL` | `true` si usas el puerto `465` |

Si `SMTP_HOST` queda vacío, los correos se omiten y solo se registran en logs.

### IA
| Variable | Valor para producción |
| --- | --- |
| `LLM_PROVIDER` | `gemini` |
| `LLM_PROVIDER_ORDER` | `gemini,openai,anthropic` |
| `GEMINI_API_KEY` | `<google-ai-studio-key>` |
| `GEMINI_MODEL` | `gemini-2.5-flash` (o el modelo vigente de tu cuenta) |
| `OPENAI_API_KEY` | `<openai-key>` (fallback opcional) |
| `LLM_MODEL` | `gpt-4.1-mini` (modelo de OpenAI, no de Gemini) |
| `ANTHROPIC_API_KEY` | `<anthropic-key>` (fallback opcional) |
| `ANTHROPIC_MODEL` | `claude-sonnet-4-20250514` |

`LLM_PROVIDER_ORDER` es el que realmente controla la cadena de intentos. Dejar al menos un proveedor con API key válida.

### Pagos con Stripe
| Variable | Valor |
| --- | --- |
| `STRIPE_SECRET_KEY` | `sk_live_...` o `sk_test_...` |
| `STRIPE_WEBHOOK_SECRET` | `whsec_...` |

Webhook en Stripe: `https://nexora-web-g9td.onrender.com/api/billing/webhook/stripe`, evento `checkout.session.completed` y eventos de suscripción que uses. Para MercadoPago/Flow, configurar además `PAYMENT_WEBHOOK_SECRET` y sus credenciales.

## 3. Antes de desplegar
1. `.venv\Scripts\ruff.exe check src tests`
2. `$env:PYTHONPATH='D:\Nexora'; .venv\Scripts\pytest.exe -q`
3. `npm --prefix client run build`
4. `npm run test:e2e`
5. `git push origin main`

## 4. Después de desplegar
1. Abrir `/health/ready` y confirmar `database: connected`.
2. Abrir `/version` y comparar `commit` con el último push.
3. Recargar con `Ctrl+F5` para invalidar el bundle anterior.
4. Probar login email/password y Google.
5. Solicitar recuperación de contraseña y confirmar recepción del correo SMTP.
6. Subir un documento y confirmar que la IA procesa o devuelve `temporary_error` reintentable.
7. Probar `POST /api/enterprise/onboarding/demo` y confirmar 12 meses de historial.
8. Revisar footer, banner, oportunidades, reporte PDF y link compartible.
9. Confirmar que Slack/Webhook/Google Workspace aparecen como Próximamente y no ejecutan acciones.
10. Confirmar que el archivo subido queda en el bucket `nexora-documents`.

## 5. Migraciones incluidas en el archivo consolidado
- `007_price_catalog.sql`: catálogo de precios con margen.
- `008_alert_config.sql`: configuración de alertas.
- `009_ai_usage.sql`: uso y costo estimado de IA.
- `010_canonical_products.sql`: catálogo canónico y alias de productos.
- `011_savings_tracking.sql`: seguimiento de ahorro capturado.
- `012_ai_privacy.sql`: consentimiento, minimización y retención de datos IA.
- `013_plan_alignment.sql`: Enterprise alineado a `150000 CLP/mes`.
- `014_ai_temporary_errors.sql`: estado `temporary_error` y reintentos ante saturación de IA.

## 6. Verificación adicional
1. Revisar en Supabase que existan las columnas IA en `organizations`.
2. Confirmar en Render que `PAYMENT_PROVIDER` no sea `mock` y que `SECRET_ENCRYPTION_KEY` esté cargada.
3. Verificar que el arranque aplique retención IA o ejecutar `POST /api/enterprise/security/purge-ai`.
4. Confirmar que `SECRET_ENCRYPTION_KEY` no cambió después de guardar integraciones; si cambia, los secretos cifrados deben volver a ingresarse.
5. Revisar logs de Render para errores de SMTP, reCAPTCHA, OAuth o LLM tras el primer uso real.
