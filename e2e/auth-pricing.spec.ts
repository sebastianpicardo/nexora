import { test, expect, type Page } from '@playwright/test';

const PLANS = [
  {
    id: 'free',
    name: 'Free',
    description: 'Para probar la auditoría con un volumen acotado.',
    price_monthly: 0,
    currency: 'USD',
    document_limit: 25,
    features: ['25 documentos al mes', 'Auditoría de precios'],
    sort_order: 10,
  },
  {
    id: 'pro',
    name: 'Pro',
    description: 'Para equipos de compras que necesitan control continuo.',
    price_monthly: 49,
    currency: 'USD',
    document_limit: 500,
    features: ['500 documentos al mes', 'Equipo con roles'],
    sort_order: 20,
  },
  {
    id: 'enterprise',
    name: 'Enterprise',
    description: 'Para operaciones multi-sucursal y alto volumen.',
    price_monthly: 199,
    currency: 'USD',
    document_limit: null,
    features: ['Documentos ilimitados', 'Panel multi-tenant'],
    sort_order: 30,
  },
];

const USER = {
  id: '11111111-1111-1111-1111-111111111111',
  org_id: '22222222-2222-2222-2222-222222222222',
  email: 'ana@empresa.com',
  name: 'Ana Pérez',
  avatar_url: '',
  role: 'owner',
  job_title: '',
  phone: '',
  timezone: 'America/Santiago',
  notify_quota: true,
  notify_weekly: true,
  active: true,
  last_login_at: null,
  created_at: '2026-01-01T00:00:00Z',
};

const ORGANIZATION = {
  id: USER.org_id,
  name: 'Empresa Demo',
  slug: 'empresa-demo',
  price_spike_threshold_pct: 10,
  min_confidence: 0.75,
  default_currency: 'USD',
};

const SUMMARY = {
  subscription: {
    id: '33333333-3333-3333-3333-333333333333',
    plan_id: 'free',
    plan_name: 'Free',
    status: 'active',
    current_period_start: '2026-01-01',
    current_period_end: '2026-02-01',
    trial_ends_at: null,
  },
  usage: {
    used: 0,
    limit: 25,
    remaining: 25,
    percentage: 0,
    unlimited: false,
    period_start: '2026-01-01',
    period_end: '2026-02-01',
    warning: false,
    exceeded: false,
  },
  plans: PLANS,
};

async function mockApi(page: Page) {
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    const json = (body: unknown, status = 200) =>
      route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });

    if (path === '/api/auth/me') {
      return json({ detail: 'No autenticado' }, 401);
    }
    if (path === '/api/billing/plans') {
      return json(PLANS);
    }
    if (path === '/api/billing/summary') {
      return json(SUMMARY);
    }
    if (path === '/api/auth/register' || path === '/api/auth/login') {
      return json({ success: true, user: USER, organization: ORGANIZATION });
    }
    return json({});
  });
}

test.beforeEach(async ({ page }) => {
  await mockApi(page);
});

test('muestra la tabla de precios con los tres planes', async ({ page }) => {
  await page.goto('/');

  await expect(page.getByRole('heading', { name: /Empieza gratis/ })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Free', exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Pro', exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Enterprise', exact: true })).toBeVisible();
  await expect(page.getByText('Más popular')).toBeVisible();
});

test('valida el email antes de enviar el formulario', async ({ page }) => {
  await page.goto('/');

  await page.getByLabel('Email corporativo').fill('no-es-un-email');
  await page.getByLabel('Contraseña').fill('Segura123');
  await page.getByRole('button', { name: 'Ingresar con email' }).click();

  await expect(page.getByRole('alert')).toContainText('Ingresa un email válido');
});

test('registra una cuenta y envía el payload esperado', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('tab', { name: 'Crear cuenta' }).click();

  await page.getByLabel('Nombre completo').fill('Ana Pérez');
  await page.getByLabel('Email corporativo').fill('ana@empresa.com');
  await page.getByLabel('Contraseña').fill('Segura123');

  const registerRequest = page.waitForRequest(
    (request) => request.url().includes('/api/auth/register') && request.method() === 'POST',
  );
  await page.getByRole('button', { name: 'Crear cuenta gratis' }).click();

  const request = await registerRequest;
  expect(request.postDataJSON()).toMatchObject({
    name: 'Ana Pérez',
    email: 'ana@empresa.com',
    password: 'Segura123',
  });
  await expect(page.getByRole('tab', { name: 'Iniciar sesión' })).toHaveCount(0);
});

test('la CTA de la tabla de precios lleva al registro', async ({ page }) => {
  await page.goto('/');

  await page.getByRole('button', { name: 'Crear cuenta con Pro' }).click();

  await expect(page.getByRole('tab', { name: 'Crear cuenta' })).toHaveAttribute(
    'aria-selected',
    'true',
  );
  await expect(page.getByLabel('Nombre completo')).toBeVisible();
});
