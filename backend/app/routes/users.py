from typing import Annotated

from fastapi import Body, Depends
from fastapi.routing import APIRouter
from sqlalchemy.orm import Session

from app.crud import user as crud_user
from app.deps import get_db_session
from app.schemas import UserCreate, UserPublic

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserPublic, status_code=201)
def register_user(
    db_session: Annotated[Session, Depends(get_db_session)],
    user_in: Annotated[UserCreate, Body()],
):
    new_user = crud_user.create_user(
        db_session=db_session,
        user_in=user_in,
    )
    return new_user
