"""DualSoul Quick Start Example.

This script demonstrates the DualSoul API programmatically.
Make sure the server is running: python -m dualsoul
"""

import httpx

BASE = "http://localhost:8000"


def main():
    # 1. Register two users
    print("=== Registering users ===")
    alice = httpx.post(f"{BASE}/api/auth/register", json={
        "username": "alice", "password": "alice123", "display_name": "Alice"
    }).json()
    print(f"Alice: {alice['data']['user_id']}")

    bob = httpx.post(f"{BASE}/api/auth/register", json={
        "username": "bob", "password": "bob123", "display_name": "Bob"
    }).json()
    print(f"Bob: {bob['data']['user_id']}")

    alice_h = {"Authorization": f"Bearer {alice['data']['token']}"}
    bob_h = {"Authorization": f"Bearer {bob['data']['token']}"}

    # 2. Set Bob's twin personality
    print("\n=== Setting Bob's twin personality ===")
    httpx.put(f"{BASE}/api/identity/profile", json={
        "twin_personality": "friendly and analytical, loves technology",
        "twin_speech_style": "casual, uses short sentences"
    }, headers=bob_h)
    print("Done!")

    # 3. Alice adds Bob as a friend
    print("\n=== Alice adds Bob ===")
    resp = httpx.post(f"{BASE}/api/social/friends/add",
                      json={"friend_username": "bob"}, headers=alice_h).json()
    print(f"Friend request: {resp}")

    # 4. Bob accepts
    print("\n=== Bob accepts ===")
    friends = httpx.get(f"{BASE}/api/social/friends", headers=bob_h).json()
    conn_id = friends["friends"][0]["conn_id"]
    httpx.post(f"{BASE}/api/social/friends/respond",
               json={"conn_id": conn_id, "action": "accept"}, headers=bob_h)
    print("Accepted!")

    # 5. Alice sends a Real → Real message
    print("\n=== Real → Real message ===")
    resp = httpx.post(f"{BASE}/api/social/messages/send", json={
        "to_user_id": bob["data"]["user_id"],
        "content": "Hey Bob! How's it going?",
        "sender_mode": "real",
        "receiver_mode": "real"
    }, headers=alice_h).json()
    print(f"Sent: {resp['msg_id']}")
    print(f"AI reply: {resp['ai_reply']}")  # None for real mode

    # 6. Alice sends a Real → Twin message (talks to Bob's twin)
    print("\n=== Real → Twin message (Bob's twin auto-replies) ===")
    resp = httpx.post(f"{BASE}/api/social/messages/send", json={
        "to_user_id": bob["data"]["user_id"],
        "content": "Hey Bob's twin, what do you think about AI?",
        "sender_mode": "real",
        "receiver_mode": "twin"
    }, headers=alice_h).json()
    print(f"Sent: {resp['msg_id']}")
    if resp.get("ai_reply"):
        print(f"Twin replied: {resp['ai_reply']['content']}")
    else:
        print("(No AI backend configured, twin used fallback)")

    # 7. Check conversation history
    print("\n=== Conversation history ===")
    msgs = httpx.get(
        f"{BASE}/api/social/messages?friend_id={bob['data']['user_id']}",
        headers=alice_h
    ).json()
    for m in msgs["messages"]:
        mode = f"[{m['sender_mode']}→{m['receiver_mode']}]"
        ai = " (AI)" if m["ai_generated"] else ""
        print(f"  {mode}{ai}: {m['content']}")

    print("\n=== Done! ===")
    print("Open http://localhost:8000 in your browser for the full demo.")


if __name__ == "__main__":
    main()
