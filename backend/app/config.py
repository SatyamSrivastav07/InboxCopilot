from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


class ConfigurationError(RuntimeError):
    """Raised when a required runtime setting is missing."""


@dataclass(frozen=True)
class Settings:
    mistral_api_key: str | None
    mistral_model: str
    frontend_origins: tuple[str, ...]
    frontend_url: str
    google_client_id: str | None
    google_client_secret: str | None
    google_redirect_uri: str
    gmail_token_file: Path
    database_url: str | None
    chroma_persist_directory: Path = Path("data/chromadb")
    chroma_collection_name: str = "inbox_emails"
    rag_top_k: int = 4
    rag_score_threshold: float = 0.2
    email_chunk_size: int = 1000
    email_chunk_overlap: int = 100

    def require_mistral_api_key(self) -> str:
        if not self.mistral_api_key:
            raise ConfigurationError(
                "MISTRAL_API_KEY is not configured. Copy .env.example to .env and add your key."
            )
        return self.mistral_api_key

    def require_google_oauth(self) -> tuple[str, str]:
        if not self.google_client_id or not self.google_client_secret:
            raise ConfigurationError(
                "Google OAuth is not configured. Set GOOGLE_CLIENT_ID and "
                "GOOGLE_CLIENT_SECRET in backend/.env."
            )
        return self.google_client_id, self.google_client_secret

    def require_database_url(self) -> str:
        if not self.database_url:
            raise ConfigurationError(
                "DATABASE_URL is not configured. Add the PostgreSQL connection URL to backend/.env."
            )
        return self.database_url


@lru_cache
def get_settings() -> Settings:
    backend_dir = Path(__file__).resolve().parents[1]
    load_dotenv(backend_dir / ".env")
    origins = os.getenv(
        "FRONTEND_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    )
    token_file_value = os.getenv("GMAIL_TOKEN_FILE", "token.json")
    token_file = Path(token_file_value)
    if not token_file.is_absolute():
        token_file = backend_dir / token_file
    chroma_directory = Path(os.getenv("CHROMA_PERSIST_DIRECTORY", "./data/chromadb"))
    if not chroma_directory.is_absolute():
        chroma_directory = backend_dir / chroma_directory

    return Settings(
        mistral_api_key=os.getenv("MISTRAL_API_KEY"),
        mistral_model=os.getenv("MISTRAL_MODEL", "mistral-small-latest"),
        frontend_origins=tuple(origin.strip() for origin in origins.split(",") if origin.strip()),
        frontend_url=os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/"),
        google_client_id=os.getenv("GOOGLE_CLIENT_ID"),
        google_client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
        google_redirect_uri=os.getenv(
            "GOOGLE_REDIRECT_URI", "http://localhost:8000/api/gmail/callback"
        ),
        gmail_token_file=token_file,
        database_url=os.getenv("DATABASE_URL"),
        chroma_persist_directory=chroma_directory,
        chroma_collection_name=os.getenv("CHROMA_COLLECTION_NAME", "inbox_emails"),
        rag_top_k=int(os.getenv("RAG_TOP_K", "4")),
        rag_score_threshold=float(os.getenv("RAG_SCORE_THRESHOLD", "0.2")),
        email_chunk_size=int(os.getenv("EMAIL_CHUNK_SIZE", "1000")),
        email_chunk_overlap=int(os.getenv("EMAIL_CHUNK_OVERLAP", "100")),
    )
