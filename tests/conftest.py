"""DualSoul test configuration."""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient

# Set test database before importing app
_tmpdir = tempfile.mkdtemp()
os.environ["DUALSOUL_DATABASE_PATH"] = os.path.join(_tmpdir, "test.db")
os.environ["DUALSOUL_JWT_SECRET"] = "test_secret_for_testing_only_32bytes!"


@pytest.fixture(scope="session")
def app():
    from dualsoul.main import app as _app
    return _app


@pytest.fixture(scope="session")
def client(app):
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture(scope="session")
def alice_token(client):
    """Register Alice and return her token."""
    resp = client.post("/api/auth/register", json={
        "username": "alice", "password": "alice123", "display_name": "Alice"
    })
    return resp.json()["data"]["token"]


@pytest.fixture(scope="session")
def bob_token(client):
    """Register Bob and return his token."""
    resp = client.post("/api/auth/register", json={
        "username": "bob", "password": "bob123", "display_name": "Bob"
    })
    return resp.json()["data"]["token"]


@pytest.fixture
def alice_h(alice_token):
    return {"Authorization": f"Bearer {alice_token}"}


@pytest.fixture
def bob_h(bob_token):
    return {"Authorization": f"Bearer {bob_token}"}
