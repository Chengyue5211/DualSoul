"""DualSoul Protocol — Dual Identity Message Format.

Every message in DualSoul carries two identity modes:
  - sender_mode: Is the sender speaking as their real self or digital twin?
  - receiver_mode: Is the message addressed to the real person or their twin?

This creates four distinct conversation modes:

  Real → Real   : Traditional human-to-human messaging
  Real → Twin   : Asking someone's digital twin a question
  Twin → Real   : Your twin reaching out to a real person
  Twin → Twin   : Autonomous twin-to-twin conversation
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class IdentityMode(str, Enum):
    REAL = "real"
    TWIN = "twin"


class ConversationMode(str, Enum):
    REAL_TO_REAL = "real_to_real"
    REAL_TO_TWIN = "real_to_twin"
    TWIN_TO_REAL = "twin_to_real"
    TWIN_TO_TWIN = "twin_to_twin"


class MessageType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    VOICE = "voice"
    SYSTEM = "system"


@dataclass
class DualSoulMessage:
    """A message in the DualSoul protocol."""

    msg_id: str
    from_user_id: str
    to_user_id: str
    sender_mode: IdentityMode
    receiver_mode: IdentityMode
    content: str
    msg_type: MessageType = MessageType.TEXT
    ai_generated: bool = False
    created_at: Optional[str] = None

    @property
    def conversation_mode(self) -> ConversationMode:
        """Determine which of the four conversation modes this message belongs to."""
        key = f"{self.sender_mode.value}_to_{self.receiver_mode.value}"
        return ConversationMode(key)

    def to_dict(self) -> dict:
        return {
            "msg_id": self.msg_id,
            "from_user_id": self.from_user_id,
            "to_user_id": self.to_user_id,
            "sender_mode": self.sender_mode.value,
            "receiver_mode": self.receiver_mode.value,
            "content": self.content,
            "msg_type": self.msg_type.value,
            "ai_generated": self.ai_generated,
            "conversation_mode": self.conversation_mode.value,
            "created_at": self.created_at,
        }


def get_conversation_mode(sender_mode: str, receiver_mode: str) -> ConversationMode:
    """Get the conversation mode from sender and receiver mode strings."""
    return ConversationMode(f"{sender_mode}_to_{receiver_mode}")
