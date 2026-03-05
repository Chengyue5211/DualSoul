"""DualSoul Pydantic models."""

from pydantic import BaseModel


# Auth
class RegisterRequest(BaseModel):
    username: str
    password: str
    display_name: str = ""


class LoginRequest(BaseModel):
    username: str
    password: str


# Identity
class SwitchModeRequest(BaseModel):
    mode: str  # 'real' or 'twin'


class UpdateProfileRequest(BaseModel):
    display_name: str = ""
    twin_personality: str = ""
    twin_speech_style: str = ""


# Social
class AddFriendRequest(BaseModel):
    friend_username: str


class RespondFriendRequest(BaseModel):
    conn_id: str
    action: str  # 'accept' or 'block'


class SendMessageRequest(BaseModel):
    to_user_id: str
    content: str
    sender_mode: str = "real"
    receiver_mode: str = "real"
    msg_type: str = "text"
