# Checklist de redeploy

## Variables obligatorias en Render
- `APP_ENV=production`
- `PAYMENT_PROVIDER=stripe` (o `mercadopago`/`flow`), nunca `mock`.
- `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` y `PAYMENT_WEBHOOK_SECRET` si se usa Stripe.
- `SESSION_SECRET` y `JWT_SECRET` con al menos 32 caracteres.
- `SECRET_ENCRYPTION_KEY` recomendado para cifrar secretos de webhooks en reposo.
- `COOKIE_SECURE=true`.
- `DATABASE_URL` de Supabase.
- `STORAGE_BACKEND=local` o `supabase` con sus credenciales.
- `RENDER_GIT_COMMIT` lo inyecta Render; el footer lo muestra vía `/version`.

## Antes de desplegar
1. `python -m ruff check src`
2. `python -m pytest`
3. `cd client && npm run build`
4. `git push origin main`

## Después de desplegar
1. Abrir `/health/ready` y confirmar `database: connected`.
2. Abrir `/version` y comparar `commit` con el último push.
3. Recargar con `Ctrl+F5` para invalidar el bundle anterior.
4. Probar login email/password y Google.
5. Probar `POST /api/enterprise/onboarding/demo` y confirmar 12 meses de historial.
6. Revisar footer, banner, oportunidades, reporte PDF y link compartible.
7. Confirmar que Slack/Webhook/Google Workspace aparecen como Próximamente y no ejecutan acciones.

## Migraciones recientes
- `010_canonical_products.sql`: catálogo canónico y alias de productos.
- `011_savings_tracking.sql`: seguimiento de ahorro capturado.
- `012_ai_privacy.sql`: consentimiento, minimización y retención de datos IA.
- `013_plan_alignment.sql`: Enterprise alineado a `150000 CLP/mes`.

## Verificación adicional
1. Ejecutar `python -m pytest -q` y `python -m ruff check src tests`.
2. Ejecutar `npm run test:e2e` para login, precios y demo guiada.
3. Revisar en Supabase que existan las columnas IA en `organizations`.
4. Confirmar en Render que `PAYMENT_PROVIDER` no sea `mock` y que `SECRET_ENCRYPTION_KEY` esté cargada.
5. Verificar que el arranque aplique retención IA o ejecutar `POST /api/enterprise/security/purge-ai`.
