from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.analyze import router as analyze_router
from app.api.chat import router as chat_router
from app.api.dashboard import router as dashboard_router
from app.api.emails import router as emails_router
from app.api.gmail import router as gmail_router
from app.api.meetings import router as meetings_router
from app.api.search import router as search_router
from app.api.tasks import router as tasks_router
from app.config import ConfigurationError, get_settings
from app.database.errors import (
    DatabaseUnavailableError,
    PersistenceError,
    RecordNotFoundError,
)
from app.gmail.errors import (
    GmailAPIError,
    GmailNotConnectedError,
    GmailOAuthError,
    GmailParseError,
    GmailRateLimitError,
)
from app.genai.rag import RAGGenerationError
from app.vectorstore.errors import VectorStoreError


def create_app() -> FastAPI:
    app = FastAPI(title="AI Inbox Copilot API", version="0.4.0")
    settings = get_settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.frontend_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )
    app.include_router(analyze_router)
    app.include_router(gmail_router)
    app.include_router(emails_router)
    app.include_router(tasks_router)
    app.include_router(meetings_router)
    app.include_router(dashboard_router)
    app.include_router(search_router)
    app.include_router(chat_router)

    @app.exception_handler(ConfigurationError)
    async def configuration_error_handler(
        _request: Request, exc: ConfigurationError
    ) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.exception_handler(GmailNotConnectedError)
    async def gmail_not_connected_handler(
        _request: Request, exc: GmailNotConnectedError
    ) -> JSONResponse:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    @app.exception_handler(GmailRateLimitError)
    async def gmail_rate_limit_handler(
        _request: Request, exc: GmailRateLimitError
    ) -> JSONResponse:
        return JSONResponse(status_code=429, content={"detail": str(exc)})

    @app.exception_handler(GmailOAuthError)
    async def gmail_oauth_error_handler(
        _request: Request, exc: GmailOAuthError
    ) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(GmailParseError)
    async def gmail_parse_error_handler(
        _request: Request, exc: GmailParseError
    ) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(GmailAPIError)
    async def gmail_api_error_handler(
        _request: Request, exc: GmailAPIError
    ) -> JSONResponse:
        return JSONResponse(status_code=502, content={"detail": str(exc)})

    @app.exception_handler(RecordNotFoundError)
    async def record_not_found_handler(
        _request: Request, exc: RecordNotFoundError
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(DatabaseUnavailableError)
    async def database_unavailable_handler(
        _request: Request, exc: DatabaseUnavailableError
    ) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.exception_handler(PersistenceError)
    async def persistence_error_handler(
        _request: Request, exc: PersistenceError
    ) -> JSONResponse:
        return JSONResponse(status_code=500, content={"detail": str(exc)})

    @app.exception_handler(VectorStoreError)
    async def vector_store_error_handler(
        _request: Request, exc: VectorStoreError
    ) -> JSONResponse:
        return JSONResponse(status_code=502, content={"detail": str(exc)})

    @app.exception_handler(RAGGenerationError)
    async def rag_generation_error_handler(
        _request: Request, exc: RAGGenerationError
    ) -> JSONResponse:
        return JSONResponse(status_code=502, content={"detail": str(exc)})

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
