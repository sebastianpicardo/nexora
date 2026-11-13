from __future__ import annotations

import asyncio

from src.services import native_integrations_service as ni


def test_native_integration_status_is_not_reversed():
    data = asyncio.run(ni.list_native_integrations({}))
    providers = {item["provider"]: item for item in data["providers"]}

    assert providers["chilecompra"]["available"] is True
    assert providers["chilecompra"]["status"] == "Referencia"
    assert providers["slack"]["available"] is False
    assert providers["slack"]["status"] == "Próximamente"


def test_unavailable_native_actions_are_disabled():
    data = asyncio.run(ni.list_native_integrations({}))
    providers = {item["provider"]: item for item in data["providers"]}

    assert all(action["enabled"] is False for action in providers["slack"]["actions"])
    assert all(action["enabled"] is False for action in providers["webhook"]["actions"])
    assert all(action["enabled"] is False for action in providers["google_workspace"]["actions"])
    assert any(action["enabled"] for action in providers["chilecompra"]["actions"])
