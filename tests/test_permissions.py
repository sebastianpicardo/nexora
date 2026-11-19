from __future__ import annotations

import pytest

from src.api.deps import ROLE_GRANTS


@pytest.mark.parametrize(
    ("role", "allowed", "denied"),
    [
        ("viewer", {"viewer"}, {"user", "analyst", "auditor", "admin", "owner"}),
        ("user", {"user", "viewer"}, {"analyst", "auditor", "admin", "owner"}),
        ("auditor", {"auditor", "viewer"}, {"user", "analyst", "admin", "owner"}),
        ("analyst", {"analyst", "user", "viewer"}, {"auditor", "admin", "owner"}),
        ("admin", {"admin", "analyst", "user", "auditor", "viewer"}, {"owner"}),
        ("owner", {"owner", "admin", "analyst", "user", "auditor", "viewer"}, set()),
    ],
)
def test_role_grants_are_explicit_and_not_escalated(role, allowed, denied):
    grants = ROLE_GRANTS[role]

    assert grants == allowed
    assert not grants & denied
