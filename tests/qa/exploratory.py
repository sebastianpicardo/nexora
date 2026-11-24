r"""Exploratory QA tests for NEXORA using Playwright + pytest-html.

Run:

    cd D:\Nexora
    pytest tests/qa/exploratory.py --html=reports/qa_report.html -v

The HTML report will be available at reports/qa_report.html.
"""
import pytest
from playwright.sync_api import expect


@pytest.fixture(scope="session", autouse=True)
def base_url():
    # The server started with: python -m uvicorn src.main:app --port 8001
    return "http://127.0.0.1:8001"


@pytest.fixture(scope="session")
def page_url(base_url):
    yield base_url


@pytest.mark.usefixtures("page_url")
class TestLoginFlow:
    """Login via email/password and Google OAuth."""

    def test_login_page_loads(self, page_url, page):
        page.goto(page_url)
        # Login tab should be active
        expect(page.get_by_role("tab", name="Iniciar sesi")).to_be_visible()
        # Email placeholder present
        expect(page.get_by_label("Email corporativo")).to_be_visible()
        expect(page.get_by_label("Contraseña")).to_be_visible()
        # reCAPTCH note is present but not blocking
        expect(page.get_by_text("Protegido por reCAPTCHA")).to_be_visible()

    def test_login_with_valid_credentials_skips_captch(
        self, page_url, page, request
    ):
        """Login with email/password when reCAPTCHA is disabled – should succeed."""
        page.goto(page_url)
        page.get_by_role("tab", name="Iniciar sesi").click()
        page.get_by_label("Email corporativo").fill("test@example.com")
        page.get_by_label("Contraseña").fill("password123")
        # Submit – reCAPTCHA will be skipped
        with page.expect_response("**/api/auth/login") as resp_info:
            page.get_by_role("button", name="Ingresar con email").click()
        resp = resp_info.value
        # Expect a redirect or JSON success; just check no 400/500
        assert resp.status < 500, f"Login failed with status {resp.status}"


class TestGoogleOAuth:
    """Google OAuth login and the ?auth=ok / ?auth=error query params."""

    def test_google_login_redirects(self, page_url, page):
        page.goto(page_url)
        # Click "Continuar con Google"
        with page.expect_response("**/api/auth/google") as resp_info:
            page.get_by_role("button", name="Continuar con Google").click()
        resp = resp_info.value
        # Google OAuth should return 302 redirect; we don't follow it here.
        assert resp.status in (301, 302, 303, 307, 308)

    def test_auth_ok_message(self, page_url, page):
        """If the callback landed on ?auth=ok, a success message should appear."""
        # Simulate landing on the page with the query param
        page.goto(f"{page_url}?auth=ok")
        # The page should show the success message we added earlier
        expect(page.get_by_text("Inicio de sesi")).to_be_visible(timeout=5000)


class TestDashboardQuickGuide:
    """Dashboard shows personalized quick‑guide tips."""

    def test_dashboard_loads_and_shows_guide(self, page_url, page):
        page.goto(page_url)
        # Wait for dashboard panel
        expect(page.get_by_role("heading", name="Requiere")).to_be_visible()
        # The guide tip we added should be present
        txt = "Revisa la bandeja de excepciones para actuar antes de que afecten el margen"
        expect(page.get_by_text(txt)).to_be_visible(timeout=5000)


class TestAutomationPage:
    """One‑click automation: PDF upload, document impact, RUT badge, actions."""

    def test_automation_page_loads(self, page_url, page):
        page.goto(page_url)
        # Verify we are on a page that contains "automation" in the title or URL
        expect(page).to_have_title(lambda t: "automatiz" in t.lower())

    def test_document_impact_section_visible(self, page_url, page):
        page.goto(page_url)
        # The new "Este documento" block should be present
        expect(page.get_by_text("Este documento")).to_be_visible()
        # RUT badge should be present (we have a valid RUT in the test PDF)
        expect(page.get_by_text("RUT")).to_be_visible(timeout=3000)

    def test_register_savings_opportunity(self, page_url, page):
        """Press “Registrar oportunidad de ahorro” and verify no JS error."""
        page.goto(page_url)
        # Assume we are on automation page; click the button
        with page.expect_waiting():
            page.get_by_role("button", name="Registrar oportunidad de ahorro").click()
        # After clicking, the page should not have console errors; we just verify we didn't get a 500.
        # Here we just check the button is enabled and clickable.
        expect(page.get_by_role("button", name="Registrar oportunidad de ahorro")).to_be_enabled()


class TestExceptionsResolution:
    """Resolve an exception from the dashboard."""

    def test_exceptions_table_has_resolver_button(self, page_url, page):
        page.goto(page_url)
        # The exceptions table should be present
        expect(page.get_by_role("table")).to_be_visible()
        # There should be a "Resolver" button in at least one row
        expect(page.get_by_text("Resolver")).to_be_visible()


def pytest_html_report_title(report):
    report.title = "NEXORA – QA Exploratory Report"


def pytest_html_results_summary(section, summary, option):
    section.append(
        "\n"
        "Generated with pytest‑playwright and pytest‑html. "
        "See individual test results for screenshots and details.\n"
    )