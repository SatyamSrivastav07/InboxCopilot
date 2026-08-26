from __future__ import annotations

import pytest

from app.config import ConfigurationError, Settings


def test_settings_accept_comma_separated_cors_origins(tmp_path):
    settings = Settings(
        frontend_origins="http://localhost:5173, http://127.0.0.1:5173",
        frontend_url="http://localhost:5173/",
        gmail_token_file=tmp_path / "token.json",
        chroma_persist_directory=tmp_path / "chroma",
    )

    assert settings.frontend_origins == ("http://localhost:5173", "http://127.0.0.1:5173")
    assert settings.frontend_url == "http://localhost:5173"


def test_production_configuration_rejects_unsafe_cors(tmp_path):
    settings = Settings(
        app_env="production",
        database_url="postgresql+psycopg2://user:pass@db.example.test:5432/inbox",
        mistral_api_key="eval-key",
        google_client_id="client-id",
        google_client_secret="client-secret",
        frontend_origins="*",
        frontend_url="https://app.example.test",
        token_encryption_key="test-encryption-key",
        session_secret="test-session-secret",
        gmail_token_file=tmp_path / "token.json",
        chroma_persist_directory=tmp_path / "chroma",
    )

    with pytest.raises(ConfigurationError, match="FRONTEND_ORIGINS"):
        settings.validate_production_requirements()


def test_production_configuration_accepts_complete_safe_values(tmp_path):
    settings = Settings(
        app_env="production",
        database_url="postgresql+psycopg2://user:pass@db.example.test:5432/inbox",
        mistral_api_key="eval-key",
        google_client_id="client-id",
        google_client_secret="client-secret",
        frontend_origins="https://app.example.test",
        frontend_url="https://app.example.test",
        token_encryption_key="test-encryption-key",
        session_secret="test-session-secret",
        gmail_token_file=tmp_path / "token.json",
        chroma_persist_directory=tmp_path / "chroma",
    )

    settings.validate_production_requirements()
