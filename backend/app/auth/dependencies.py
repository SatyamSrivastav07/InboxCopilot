from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database.dependencies import get_db
from app.database.models.user import UserRecord
from app.database.repositories.user_repository import UserRepository


def get_current_user(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> UserRecord:
    user_id = request.session.get("user_id")
    if not isinstance(user_id, int):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sign in with Google before accessing an inbox.",
        )
    user = UserRepository(db).get(user_id)
    if user is None or user.status != "active":
        request.session.clear()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your session has expired. Sign in with Google again.",
        )
    return user


CurrentUser = Annotated[UserRecord, Depends(get_current_user)]
