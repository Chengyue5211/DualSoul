"""Identity switching and profile tests."""


def test_switch_to_twin(client, alice_h):
    resp = client.post("/api/identity/switch", json={"mode": "twin"}, headers=alice_h)
    assert resp.status_code == 200
    assert resp.json()["mode"] == "twin"


def test_switch_to_real(client, alice_h):
    resp = client.post("/api/identity/switch", json={"mode": "real"}, headers=alice_h)
    assert resp.json()["mode"] == "real"


def test_switch_invalid_mode(client, alice_h):
    resp = client.post("/api/identity/switch", json={"mode": "ghost"}, headers=alice_h)
    assert resp.json()["success"] is False


def test_switch_requires_auth(client):
    resp = client.post("/api/identity/switch", json={"mode": "twin"})
    assert resp.status_code == 401


def test_get_profile(client, alice_h):
    resp = client.get("/api/identity/me", headers=alice_h)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["username"] == "alice"
    assert data["display_name"] == "Alice"
    assert data["current_mode"] in ("real", "twin")


def test_update_twin_personality(client, alice_h):
    resp = client.put("/api/identity/profile", json={
        "twin_personality": "analytical and curious",
        "twin_speech_style": "concise and witty"
    }, headers=alice_h)
    assert resp.json()["success"] is True

    # Verify
    resp = client.get("/api/identity/me", headers=alice_h)
    data = resp.json()["data"]
    assert data["twin_personality"] == "analytical and curious"
    assert data["twin_speech_style"] == "concise and witty"


def test_update_empty_profile(client, alice_h):
    resp = client.put("/api/identity/profile", json={}, headers=alice_h)
    assert resp.json()["success"] is False
