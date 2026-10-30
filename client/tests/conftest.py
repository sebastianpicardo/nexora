from __future__ import annotations

import os

os.environ["APP_ENV"] = "test"
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-with-enough-length-123456")
os.environ.setdefault("SESSION_SECRET", "test-session-secret-with-enough-length-123456")
os.environ.setdefault("DATABASE_URL", "")

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from src.main import app

    with TestClient(app) as test_client:
        yield test_client
