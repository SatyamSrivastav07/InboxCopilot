import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.database.models import EmailDraftRecord, EmailRecord, EntityRecord, MeetingRecord, TaskRecord, UserRecord  # noqa: F401


class _NoopRateLimiter:
    def enforce(self, **_kwargs) -> None:
        return None


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with factory() as session:
        yield session
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def override_db(db_session: Session):
    def dependency():
        yield db_session

    return dependency


@pytest.fixture(autouse=True)
def authenticated_api_user():
    """Existing endpoint tests exercise business behavior after session auth."""
    from app.auth.dependencies import get_current_user
    from app.main import app
    from app.security.rate_limit_dependencies import get_rate_limiter

    app.dependency_overrides[get_current_user] = lambda: UserRecord(
        id=1, google_subject="test-subject", email="test@example.com", status="active"
    )
    app.dependency_overrides[get_rate_limiter] = lambda: _NoopRateLimiter()
    yield
    app.dependency_overrides.clear()
