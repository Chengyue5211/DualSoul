"""Twin engine tests."""

from dualsoul.protocol.message import (
    ConversationMode,
    DualSoulMessage,
    IdentityMode,
    get_conversation_mode,
)


def test_conversation_modes():
    assert get_conversation_mode("real", "real") == ConversationMode.REAL_TO_REAL
    assert get_conversation_mode("real", "twin") == ConversationMode.REAL_TO_TWIN
    assert get_conversation_mode("twin", "real") == ConversationMode.TWIN_TO_REAL
    assert get_conversation_mode("twin", "twin") == ConversationMode.TWIN_TO_TWIN


def test_message_to_dict():
    msg = DualSoulMessage(
        msg_id="sm_test123",
        from_user_id="u_alice",
        to_user_id="u_bob",
        sender_mode=IdentityMode.REAL,
        receiver_mode=IdentityMode.TWIN,
        content="Hello twin!",
    )
    d = msg.to_dict()
    assert d["sender_mode"] == "real"
    assert d["receiver_mode"] == "twin"
    assert d["conversation_mode"] == "real_to_twin"
    assert d["ai_generated"] is False


def test_message_conversation_mode():
    msg = DualSoulMessage(
        msg_id="sm_test456",
        from_user_id="u_a",
        to_user_id="u_b",
        sender_mode=IdentityMode.TWIN,
        receiver_mode=IdentityMode.TWIN,
        content="Twin chat",
        ai_generated=True,
    )
    assert msg.conversation_mode == ConversationMode.TWIN_TO_TWIN
    assert msg.ai_generated is True


def test_identity_mode_values():
    assert IdentityMode.REAL.value == "real"
    assert IdentityMode.TWIN.value == "twin"
