"""Social system tests — friends, messages, four conversation modes."""

import pytest


@pytest.fixture(scope="module")
def bob_user_id(bob_token):
    """Ensure bob is registered and extract user_id from token."""
    import jwt
    payload = jwt.decode(bob_token, options={"verify_signature": False})
    return payload["user_id"]


# ═══ Friend System ═══

def test_add_friend_requires_auth(client):
    resp = client.post("/api/social/friends/add", json={"friend_username": "bob"})
    assert resp.status_code == 401


def test_add_friend_not_found(client, alice_h):
    resp = client.post("/api/social/friends/add",
                       json={"friend_username": "nonexistent"}, headers=alice_h)
    assert resp.json()["success"] is False


def test_add_friend_success(client, alice_h, bob_user_id):
    """Alice adds Bob — bob_user_id fixture ensures Bob is registered first."""
    resp = client.post("/api/social/friends/add",
                       json={"friend_username": "bob"}, headers=alice_h)
    data = resp.json()
    assert data["success"] is True, f"add_friend failed: {data}"
    assert "conn_id" in data


def test_add_friend_duplicate(client, alice_h, bob_user_id):
    resp = client.post("/api/social/friends/add",
                       json={"friend_username": "bob"}, headers=alice_h)
    assert resp.json()["success"] is False


def test_friends_list_pending(client, bob_h):
    """Bob should see an incoming pending request."""
    resp = client.get("/api/social/friends", headers=bob_h)
    assert resp.json()["success"] is True
    friends = resp.json()["friends"]
    assert len(friends) >= 1
    assert friends[0]["status"] == "pending"
    assert friends[0]["is_incoming"] is True


# ═══ Friend Response ═══

def test_respond_requires_auth(client):
    resp = client.post("/api/social/friends/respond",
                       json={"conn_id": "sc_x", "action": "accept"})
    assert resp.status_code == 401


def test_respond_accept(client, bob_h):
    """Bob accepts Alice's friend request."""
    resp = client.get("/api/social/friends", headers=bob_h)
    pending = [f for f in resp.json()["friends"]
               if f["status"] == "pending" and f["is_incoming"]]
    assert len(pending) >= 1

    resp = client.post("/api/social/friends/respond",
                       json={"conn_id": pending[0]["conn_id"], "action": "accept"},
                       headers=bob_h)
    assert resp.json()["success"] is True
    assert resp.json()["status"] == "accepted"


# ═══ Messages ═══

def test_messages_requires_auth(client):
    resp = client.get("/api/social/messages?friend_id=u_test")
    assert resp.status_code == 401


def test_send_empty_content(client, alice_h):
    resp = client.get("/api/social/friends", headers=alice_h)
    bob = [f for f in resp.json()["friends"] if f["username"] == "bob"][0]

    resp = client.post("/api/social/messages/send", json={
        "to_user_id": bob["user_id"], "content": "  "
    }, headers=alice_h)
    assert resp.json()["success"] is False


def test_send_to_non_friend(client, alice_h):
    resp = client.post("/api/social/messages/send", json={
        "to_user_id": "u_nonexistent", "content": "hello"
    }, headers=alice_h)
    assert resp.json()["success"] is False


def test_send_real_to_real(client, alice_h):
    """Real → Real: traditional messaging."""
    resp = client.get("/api/social/friends", headers=alice_h)
    bob = [f for f in resp.json()["friends"] if f["username"] == "bob"][0]

    resp = client.post("/api/social/messages/send", json={
        "to_user_id": bob["user_id"],
        "content": "Hey Bob, how are you?",
        "sender_mode": "real",
        "receiver_mode": "real"
    }, headers=alice_h)
    assert resp.json()["success"] is True
    assert "msg_id" in resp.json()
    assert resp.json()["ai_reply"] is None  # No auto-reply in real mode


def test_send_real_to_twin(client, alice_h):
    """Real → Twin: talking to someone's twin (triggers auto-reply)."""
    resp = client.get("/api/social/friends", headers=alice_h)
    bob = [f for f in resp.json()["friends"] if f["username"] == "bob"][0]

    resp = client.post("/api/social/messages/send", json={
        "to_user_id": bob["user_id"],
        "content": "Hey Bob's twin, what do you think?",
        "sender_mode": "real",
        "receiver_mode": "twin"
    }, headers=alice_h)
    assert resp.json()["success"] is True
    reply = resp.json().get("ai_reply")
    if reply:
        assert reply["ai_generated"] is True


def test_send_twin_to_twin(client, alice_h):
    """Twin → Twin: fully autonomous conversation."""
    resp = client.get("/api/social/friends", headers=alice_h)
    bob = [f for f in resp.json()["friends"] if f["username"] == "bob"][0]

    resp = client.post("/api/social/messages/send", json={
        "to_user_id": bob["user_id"],
        "content": "Twin-to-twin test",
        "sender_mode": "twin",
        "receiver_mode": "twin"
    }, headers=alice_h)
    assert resp.json()["success"] is True


def test_messages_after_send(client, alice_h):
    """Should have messages in history now."""
    resp = client.get("/api/social/friends", headers=alice_h)
    bob = [f for f in resp.json()["friends"] if f["username"] == "bob"][0]

    resp = client.get(f"/api/social/messages?friend_id={bob['user_id']}", headers=alice_h)
    assert resp.json()["success"] is True
    assert len(resp.json()["messages"]) >= 3


def test_messages_from_bob_side(client, bob_h):
    """Bob should also see the messages."""
    resp = client.get("/api/social/friends", headers=bob_h)
    alice = [f for f in resp.json()["friends"] if f["username"] == "alice"][0]

    resp = client.get(f"/api/social/messages?friend_id={alice['user_id']}", headers=bob_h)
    assert resp.json()["success"] is True
    assert len(resp.json()["messages"]) >= 3


# ═══ Unread ═══

def test_unread_requires_auth(client):
    resp = client.get("/api/social/unread")
    assert resp.status_code == 401


def test_unread_count(client, alice_h):
    """Send a new message, then check unread for Bob."""
    resp = client.get("/api/social/friends", headers=alice_h)
    bob = [f for f in resp.json()["friends"] if f["username"] == "bob"][0]

    client.post("/api/social/messages/send", json={
        "to_user_id": bob["user_id"], "content": "unread test",
        "sender_mode": "real", "receiver_mode": "real"
    }, headers=alice_h)

    from dualsoul.auth import create_token
    bob_h2 = {"Authorization": f"Bearer {create_token(bob['user_id'], 'bob')}"}
    resp = client.get("/api/social/unread", headers=bob_h2)
    assert resp.status_code == 200
    assert resp.json()["count"] >= 1
