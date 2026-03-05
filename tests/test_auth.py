"""Auth endpoint tests."""


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_register_success(client):
    resp = client.post("/api/auth/register", json={
        "username": "testuser", "password": "test123"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "token" in data["data"]


def test_register_duplicate(client):
    resp = client.post("/api/auth/register", json={
        "username": "testuser", "password": "test123"
    })
    assert resp.json()["success"] is False


def test_register_short_password(client):
    resp = client.post("/api/auth/register", json={
        "username": "shortpw", "password": "12345"
    })
    assert resp.json()["success"] is False


def test_login_success(client):
    resp = client.post("/api/auth/login", json={
        "username": "testuser", "password": "test123"
    })
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    assert "token" in resp.json()["data"]


def test_login_wrong_password(client):
    resp = client.post("/api/auth/login", json={
        "username": "testuser", "password": "wrong"
    })
    assert resp.json()["success"] is False


def test_protected_without_token(client):
    resp = client.get("/api/identity/me")
    assert resp.status_code == 401
