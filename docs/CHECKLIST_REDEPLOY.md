# Checklist de redeploy

## Variables obligatorias en Render
- `APP_ENV=production`
- `PAYMENT_PROVIDER=stripe` (o `mercadopago`/`flow`), nunca `mock`.
- `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` y `PAYMENT_WEBHOOK_SECRET` si se usa Stripe.
- `SESSION_SECRET` y `JWT_SECRET` con al menos 32 caracteres.
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
