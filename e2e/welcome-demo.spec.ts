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

test('la demo flash avanza sola y se cierra con transición', async ({ page }) => {
  await mockDashboard(page);
  await page.goto('/');

  await expect(page.getByRole('heading', { name: 'El viaje del ahorro' })).toBeVisible();
  await page.getByRole('button', { name: /Ver demo flash/ }).click();

  const dialog = page.getByRole('dialog', { name: /Demo flash/ });
  await expect(dialog).toBeVisible();

  const progress = dialog.getByRole('progressbar', { name: /Progreso de la demo/ });
  await expect(progress).toHaveAttribute('aria-valuenow', '1');
  await expect(dialog.locator('.welcome-demo-step.active')).toHaveCount(1);
  await expect(dialog.locator('.welcome-demo-media')).toBeVisible();

  await expect(progress).toHaveAttribute('aria-valuenow', '2', { timeout: 6000 });
  await expect(dialog.locator('.welcome-demo-step').nth(1)).toHaveAttribute('aria-current', 'step');

  await dialog.getByRole('button', { name: 'Saltar introducción' }).click();
  await expect(dialog).toBeHidden();
});
