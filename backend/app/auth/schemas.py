from pydantic import BaseModel, ConfigDict


class AuthModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SessionUser(AuthModel):
    id: int
    email: str | None = None
    display_name: str | None = None
    avatar_url: str | None = None


class SessionStatus(AuthModel):
    authenticated: bool
    user: SessionUser | None = None


class GoogleAuthUrl(AuthModel):
    authorization_url: str
