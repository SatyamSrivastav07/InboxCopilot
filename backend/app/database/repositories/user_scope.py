from sqlalchemy.orm import Session

from app.database.repositories.user_repository import UserRepository


def resolve_user_id(db: Session, user_id: int | None = None) -> int:
    """Resolve explicit ownership, preserving legacy local data until Phase 10."""
    if user_id is not None:
        return user_id
    return UserRepository(db).get_or_create_legacy_user().id
