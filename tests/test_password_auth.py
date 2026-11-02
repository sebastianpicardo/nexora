from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.core.security import hash_password, sign_payload, verify_password, verify_signature
from src.schemas.auth import LoginRequest, RegisterRequest


def test_hash_password_is_salted_and_verifiable():
    first = hash_password("Segura123")
    second = hash_password("Segura123")

    assert first != second
    assert first.startswith("pbkdf2_sha256$")
    assert verify_password("Segura123", first)
    assert not verify_password("segura123", first)
    assert not verify_password("", first)
    assert not verify_password("Segura123", None)


def test_verify_password_rejects_malformed_hash():
    assert not verify_password("Segura123", "not-a-valid-hash")


def test_webhook_signature_roundtrip():
    body = b'{"event_id":"evt_1","plan_id":"pro"}'
    signature = sign_payload("super-secret", body)

    assert verify_signature("super-secret", body, signature)
    assert not verify_signature("other-secret", body, signature)
    assert not verify_signature("super-secret", body, None)


def test_register_request_normalizes_input():
    payload = RegisterRequest(
        name="  Ana   Pérez ",
        email=" ANA@Empresa.COM ",
        password="Segura123",
    )

    assert payload.name == "Ana Pérez"
    assert payload.email == "ana@empresa.com"


@pytest.mark.parametrize("password", ["short1", "sinmayus1", "SINMINUS1", "SinDigitos"])
def test_register_request_rejects_weak_passwords(password):
    with pytest.raises(ValidationError):
        RegisterRequest(name="Ana Pérez", email="ana@empresa.com", password=password)


def test_auth_requests_reject_invalid_email():
    with pytest.raises(ValidationError):
        RegisterRequest(name="Ana Pérez", email="no-es-email", password="Segura123")
    with pytest.raises(ValidationError):
        LoginRequest(email="no-es-email", password="Segura123")
