import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.auth import get_current_user, CurrentUser

FAKE_USER = CurrentUser(id="11111111-1111-1111-1111-111111111111", email="test@example.com")


@pytest.fixture
def client():
    app.dependency_overrides[get_current_user] = lambda: FAKE_USER
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def fake_user():
    return FAKE_USER