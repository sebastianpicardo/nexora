import { test, expect, type Page } from '@playwright/test';

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

const BILLING = {
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
  plans: [],
};

async function mockDashboard(page: Page) {
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    const json = (body: unknown) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });

    if (path === '/api/auth/me') {
      return json({ success: true, user: USER, organization: ORGANIZATION });
    }
    if (path === '/api/billing/summary') {
      return json(BILLING);
    }
    if (path === '/api/dashboard/summary') {
      return json({});
    }
    return json({});
  });
}

test('la bienvenida permite cargar la demo de 12 meses', async ({ page }) => {
  await mockDashboard(page);
  await page.goto('/');

  await expect(
    page.getByRole('heading', { name: 'Convierte tus documentos de compra en decisiones claras' }),
  ).toBeVisible();
  await expect(page.getByText('Cargar datos de demostración')).toBeVisible();

  const demoRequest = page.waitForRequest(
    (request) =>
      request.url().includes('/api/enterprise/onboarding/demo') && request.method() === 'POST',
  );
  await page.getByRole('button', { name: 'Cargar datos de demostración' }).click();

  const request = await demoRequest;
  expect(new URL(request.url()).pathname).toBe('/api/enterprise/onboarding/demo');
});

test('agrupa la operación en secciones con tabs internas', async ({ page }) => {
  await mockDashboard(page);
  await page.goto('/');

  await page.getByRole('button', { name: 'Bandeja de Compras' }).click();

  await expect(page.getByRole('tab', { name: 'Todos los documentos' })).toBeVisible();
  await expect(page.getByRole('tab', { name: 'Ítems auditados' })).toBeVisible();
  await expect(page.getByRole('tab', { name: 'Alertas y Excepciones' })).toBeVisible();

  await page.getByRole('tab', { name: 'Ítems auditados' }).click();
  await expect(page.getByRole('tab', { name: 'Ítems auditados' })).toHaveAttribute(
    'aria-selected',
    'true',
  );
  await expect(
    page.getByRole('heading', { name: 'Convierte tus documentos de compra en decisiones claras' }),
  ).toHaveCount(0);
});
