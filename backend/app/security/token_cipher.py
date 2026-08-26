from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from app.config import ConfigurationError, Settings


class OAuthTokenCipher:
    """Encrypt OAuth credential JSON before it reaches persistent storage."""

    def __init__(self, key: str) -> None:
        try:
            self._fernet = Fernet(key.encode("utf-8"))
        except (TypeError, ValueError) as exc:
            raise ConfigurationError("TOKEN_ENCRYPTION_KEY is not a valid Fernet key.") from exc

    @classmethod
    def from_settings(cls, settings: Settings) -> "OAuthTokenCipher":
        return cls(settings.require_token_encryption_key())

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")

    def decrypt(self, ciphertext: str) -> str:
        try:
            return self._fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise ConfigurationError("Stored Gmail credentials cannot be decrypted.") from exc
