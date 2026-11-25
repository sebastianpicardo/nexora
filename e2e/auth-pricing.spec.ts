import { test, expect, type Page } from "@playwright/test";

// Estas pruebas no dependen de un backend real: interceptan /api/** y solo
// verifican que la app (servidor Vite) carga sin errores de conexión.

async function mockUnauthenticated(page: Page) {
  await page.route("**/version", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ app: "nexora", version: "0.1.0" }),
    }),
  );
  await page.route("**/health", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "ok" }),
    }),
  );
  await page.route("**/api/**", (route) => {
    const path = new URL(route.request().url()).pathname;
    const json = (body: unknown, status = 200) =>
      route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
    if (path === "/api/auth/me") return json({ detail: "No autenticado" }, 401);
    if (path === "/api/auth/config") {
      return json({
        google_enabled: false,
        recaptcha_enabled: false,
        recaptcha_site_key: "",
        payment_provider: "mock",
      });
    }
    if (path === "/api/billing/plans") {
      return json([
        {
          id: "free",
          name: "Free",
          description: "Para probar la auditoría.",
          price_monthly: 0,
          currency: "CLP",
          document_limit: 25,
          user_limit: 1,
          features: ["25 documentos al mes", "1 usuario"],
          sort_order: 10,
        },
        {
          id: "pro",
          name: "Pro",
          description: "Para equipos.",
          price_monthly: 39990,
          currency: "CLP",
          document_limit: 500,
          user_limit: 5,
          features: ["500 documentos al mes", "Hasta 5 usuarios"],
          sort_order: 20,
        },
      ]);
    }
    if (path === "/api/billing/summary") {
      return json({
        subscription: {
          plan_id: "free",
          plan_name: "Free",
          status: "active",
          current_period_start: "2026-01-01",
          current_period_end: "2026-02-01",
        },
        usage: {
          used: 0,
          limit: 25,
          remaining: 25,
          percentage: 0,
          unlimited: false,
          period_start: "2026-01-01",
          period_end: "2026-02-01",
        },
        plans: [],
      });
    }
    return json({});
  });
}

test.beforeEach(async ({ page }) => {
  await mockUnauthenticated(page);
});

test("la landing muestra la propuesta de valor y lleva al registro", async ({ page }) => {
  await page.goto("/");

  await expect(page.locator(".landing")).toBeVisible();
  await expect(page.getByRole("heading", { level: 1 })).toContainText(/margen/i);

  await page.locator(".landing-nav").getByRole("button", { name: /Probar gratis/i }).click();

  await expect(page.getByLabel("Nombre completo")).toBeVisible();
  await expect(page.getByLabel("Contrase\u00f1a")).toBeVisible();
});

test("la página de acceso carga sin errores de conexión", async ({ page }) => {
  const connectionErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() !== "error") return;
    const text = message.text();
    if (/ERR_CONNECTION|Failed to fetch|ECONNREFUSED|net::ERR/i.test(text)) {
      connectionErrors.push(text);
    }
  });

  await page.goto("/");
  await page.locator(".landing-nav").getByRole("button", { name: "Ingresar" }).click();

  await expect(page.getByRole("tab", { name: /Iniciar sesi/i })).toBeVisible();
  await expect(page.getByLabel("Email corporativo")).toBeVisible();
  await expect(page.getByLabel("Contrase\u00f1a")).toBeVisible();

  expect(connectionErrors, connectionErrors.join("\n")).toHaveLength(0);
});

test("permite alternar a la pestaña Crear cuenta", async ({ page }) => {
  await page.goto("/");
  await page.locator(".landing-nav").getByRole("button", { name: "Ingresar" }).click();

  await page.getByRole("tab", { name: /Crear cuenta/i }).click();

  await expect(page.getByLabel("Nombre completo")).toBeVisible();
  await expect(page.getByLabel("Contrase\u00f1a")).toBeVisible();
});

test("la tabla de precios muestra precios legibles y límite de usuarios", async ({ page }) => {
  await page.goto("/");

  const pricing = page.locator(".pricing-section");
  await expect(pricing.getByRole("heading", { name: "Free", exact: true })).toBeVisible();
  await expect(pricing.getByText("Gratis", { exact: true })).toBeVisible();
  await expect(pricing.getByText(/usuario/i).first()).toBeVisible();
  // No debe existir el texto pegado tipo "Gratis$0" o "$0/mes".
  await expect(page.getByText("Gratis$0")).toHaveCount(0);
  await expect(page.getByText("$0/mes")).toHaveCount(0);
});

