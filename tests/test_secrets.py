from __future__ import annotations

from src.core.secrets import decrypt_secret, encrypt_secret


def test_encrypt_and_decrypt_roundtrip(monkeypatch):
    from src.core.config import settings

    monkeypatch.setattr(settings, "secret_encryption_key", "test-encryption-key-value-123456")
    encrypted = encrypt_secret("super-secret-webhook")

    assert encrypted.startswith("enc:v1:")
    assert encrypted != "super-secret-webhook"
    assert decrypt_secret(encrypted) == "super-secret-webhook"


def test_legacy_plaintext_secret_is_accepted(monkeypatch):
    from src.core.config import settings

    monkeypatch.setattr(settings, "secret_encryption_key", "test-encryption-key-value-123456")
    assert decrypt_secret("legacy-plain-secret") == "legacy-plain-secret"
