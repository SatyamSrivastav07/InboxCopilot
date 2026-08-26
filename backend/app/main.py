import logging
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from fastapi.responses import JSONResponse

from app.api.analyze import router as analyze_router
from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.dashboard import router as dashboard_router
from app.api.drafts import router as drafts_router
from app.api.emails import router as emails_router
from app.api.gmail import router as gmail_router
from app.api.jobs import router as jobs_router
from app.api.meetings import router as meetings_router
from app.api.search import router as search_router
from app.api.tasks import router as tasks_router
from app.config import ConfigurationError, get_settings
from app.cache.client import get_redis_client
from app.core.logging import configure_logging
from app.database.session import get_engine
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
from app.genai.query_router import QueryRoutingError
from app.genai.rag import RAGGenerationError
from app.genai.reply_chain import ReplyGenerationError
from app.services.reply_service import DraftConflictError, DraftUnsafeError
from app.services.thread_context_service import ThreadContextError
from app.services.jobs import JobNotFoundError, JobQueueUnavailableError
from app.vectorstore.errors import VectorStoreError
from sqlalchemy import text

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()
    settings.validate_production_requirements()
    configure_logging(settings.log_level)
    app = FastAPI(title="AI Inbox Copilot API", version="0.10.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.frontend_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret_for_runtime(),
        session_cookie="inbox_copilot_session",
        max_age=7 * 24 * 60 * 60,
        same_site="none" if settings.app_env == "production" else "lax",
        https_only=settings.app_env == "production",
    )

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                is_too_large = int(content_length) > settings.max_request_bytes
            except ValueError:
                is_too_large = False
            if is_too_large:
                return error_response(
                    request,
                    413,
                    "REQUEST_TOO_LARGE",
                    "Request body exceeds the configured size limit.",
                )
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "event=http_request request_id=%s method=%s path=%s status=%s",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
        )
        return response
    app.include_router(analyze_router)
    app.include_router(auth_router)
    app.include_router(gmail_router)
    app.include_router(emails_router)
    app.include_router(tasks_router)
    app.include_router(meetings_router)
    app.include_router(dashboard_router)
    app.include_router(search_router)
    app.include_router(chat_router)
    app.include_router(drafts_router)
    app.include_router(jobs_router)

    def error_response(request: Request, status_code: int, code: str, message: str) -> JSONResponse:
        return JSONResponse(
            status_code=status_code,
            content={
                "error": {
                    "code": code,
                    "message": message,
                    "request_id": getattr(request.state, "request_id", ""),
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_error_handler(
        request: Request, _exc: RequestValidationError
    ) -> JSONResponse:
        return error_response(request, 422, "VALIDATION_ERROR", "Request validation failed.")

    @app.exception_handler(HTTPException)
    async def http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
        message = str(exc.detail) if isinstance(exc.detail, str) else "The request could not be completed."
        return error_response(request, exc.status_code, "HTTP_ERROR", message)

    @app.exception_handler(ConfigurationError)
    async def configuration_error_handler(
        request: Request, exc: ConfigurationError
    ) -> JSONResponse:
        return error_response(request, 503, "CONFIGURATION_ERROR", str(exc))

    @app.exception_handler(GmailNotConnectedError)
    async def gmail_not_connected_handler(
        request: Request, exc: GmailNotConnectedError
    ) -> JSONResponse:
        return error_response(request, 401, "GMAIL_NOT_CONNECTED", str(exc))

    @app.exception_handler(GmailRateLimitError)
    async def gmail_rate_limit_handler(
        request: Request, exc: GmailRateLimitError
    ) -> JSONResponse:
        return error_response(request, 429, "GMAIL_RATE_LIMIT", str(exc))

    @app.exception_handler(GmailOAuthError)
    async def gmail_oauth_error_handler(
        request: Request, exc: GmailOAuthError
    ) -> JSONResponse:
        return error_response(request, 400, "GMAIL_OAUTH_ERROR", str(exc))

    @app.exception_handler(GmailParseError)
    async def gmail_parse_error_handler(
        request: Request, exc: GmailParseError
    ) -> JSONResponse:
        return error_response(request, 422, "GMAIL_PARSE_ERROR", str(exc))

    @app.exception_handler(GmailAPIError)
    async def gmail_api_error_handler(
        request: Request, exc: GmailAPIError
    ) -> JSONResponse:
        return error_response(request, 502, "GMAIL_API_ERROR", str(exc))

    @app.exception_handler(RecordNotFoundError)
    async def record_not_found_handler(
        request: Request, exc: RecordNotFoundError
    ) -> JSONResponse:
        return error_response(request, 404, "NOT_FOUND", str(exc))

    @app.exception_handler(DatabaseUnavailableError)
    async def database_unavailable_handler(
        request: Request, exc: DatabaseUnavailableError
    ) -> JSONResponse:
        return error_response(request, 503, "DATABASE_UNAVAILABLE", str(exc))

    @app.exception_handler(PersistenceError)
    async def persistence_error_handler(
        request: Request, exc: PersistenceError
    ) -> JSONResponse:
        return error_response(request, 500, "PERSISTENCE_ERROR", str(exc))

    @app.exception_handler(VectorStoreError)
    async def vector_store_error_handler(
        request: Request, exc: VectorStoreError
    ) -> JSONResponse:
        return error_response(request, 502, "VECTOR_STORE_ERROR", str(exc))

    @app.exception_handler(RAGGenerationError)
    async def rag_generation_error_handler(
        request: Request, exc: RAGGenerationError
    ) -> JSONResponse:
        return error_response(request, 502, "RAG_GENERATION_ERROR", str(exc))

    @app.exception_handler(QueryRoutingError)
    async def query_routing_error_handler(
        request: Request, exc: QueryRoutingError
    ) -> JSONResponse:
        return error_response(request, 502, "QUERY_ROUTING_ERROR", str(exc))

    @app.exception_handler(ReplyGenerationError)
    async def reply_generation_error_handler(
        request: Request, exc: ReplyGenerationError
    ) -> JSONResponse:
        return error_response(request, 502, "REPLY_GENERATION_ERROR", str(exc))

    @app.exception_handler(DraftConflictError)
    async def draft_conflict_error_handler(
        request: Request, exc: DraftConflictError
    ) -> JSONResponse:
        return error_response(request, 409, "DRAFT_CONFLICT", str(exc))

    @app.exception_handler(DraftUnsafeError)
    async def draft_unsafe_error_handler(
        request: Request, exc: DraftUnsafeError
    ) -> JSONResponse:
        return error_response(request, 422, "DRAFT_UNSAFE", str(exc))

    @app.exception_handler(ThreadContextError)
    async def thread_context_error_handler(
        request: Request, exc: ThreadContextError
    ) -> JSONResponse:
        return error_response(request, 422, "THREAD_CONTEXT_ERROR", str(exc))

    @app.exception_handler(JobQueueUnavailableError)
    async def job_queue_unavailable_handler(
        request: Request, exc: JobQueueUnavailableError
    ) -> JSONResponse:
        return error_response(request, 503, "JOB_QUEUE_UNAVAILABLE", str(exc))

    @app.exception_handler(JobNotFoundError)
    async def job_not_found_handler(
        request: Request, exc: JobNotFoundError
    ) -> JSONResponse:
        return error_response(request, 404, "JOB_NOT_FOUND", str(exc))

    @app.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "event=unhandled_api_error request_id=%s",
            getattr(request.state, "request_id", ""),
            exc_info=exc,
        )
        return error_response(
            request,
            500,
            "INTERNAL_ERROR",
            "The server could not complete the request.",
        )

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready", tags=["health"])
    def readiness() -> JSONResponse:
        dependencies = {"postgresql": "ok", "redis": "ok"}
        try:
            with get_engine().connect() as connection:
                connection.execute(text("SELECT 1"))
        except Exception:
            dependencies["postgresql"] = "unavailable"
        try:
            get_redis_client().ping()
        except Exception:
            dependencies["redis"] = "unavailable"
        ready = all(value == "ok" for value in dependencies.values())
        return JSONResponse(
            status_code=200 if ready else 503,
            content={"status": "ready" if ready else "not_ready", "dependencies": dependencies},
        )

    return app


app = create_app()
