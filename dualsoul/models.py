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
    preferred_lang: str = ""  # ISO 639-1: zh, en, ja, ko, fr, de, es, etc.
    twin_auto_reply: int | None = None  # 0=off, 1=on (None=no change)
    gender: str = ""  # 'male', 'female', '' (unset)


class TwinPreviewRequest(BaseModel):
    display_name: str = ""
    personality: str = ""
    speech_style: str = ""


class AvatarUploadRequest(BaseModel):
    image: str  # base64 encoded image data (data:image/png;base64,... or raw base64)
    type: str = "real"  # 'real' or 'twin'


class VoiceUploadRequest(BaseModel):
    audio: str  # base64 encoded audio data (data:audio/webm;base64,... or raw base64)


class TwinDraftRequest(BaseModel):
    friend_id: str
    incoming_msg: str
    context: list[dict] = []  # [{role: "me"/"friend", content: "..."}]


class TwinChatRequest(BaseModel):
    message: str
    history: list[dict] = []  # [{role: "me"/"twin", content: "..."}]
    image: str = ""  # Optional base64 image data URL for vision


# Social
class AddFriendRequest(BaseModel):
    friend_username: str


class RespondFriendRequest(BaseModel):
    conn_id: str
    action: str  # 'accept' or 'block'


class TranslateRequest(BaseModel):
    content: str
    source_lang: str = "auto"
    target_lang: str = "en"


class SendMessageRequest(BaseModel):
    to_user_id: str
    content: str
    sender_mode: str = "real"
    receiver_mode: str = "real"
    msg_type: str = "text"
    target_lang: str = ""  # If set, twin translates to this language with personality preservation


# Twin Import (年轮分身导入)
class TwinImportRequest(BaseModel):
    format: str = "tpf_v1"  # Twin Portable Format version
    data: dict  # Full Nianlun export payload


class TwinSyncRequest(BaseModel):
    format: str = "tpf_v1"
    since: str = ""  # ISO timestamp of last sync
    data: dict  # Incremental data (new memories, entities, dimension updates)
