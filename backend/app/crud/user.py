from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.exceptions import UserAlreadyExists
from app.models import User
from app.schemas import UserCreate


def create_user(db_session: Session, user_in: UserCreate) -> User:
    stmt = select(User).where(User.email == user_in.email)
    existing_user = db_session.execute(stmt).scalar_one_or_none()
    if existing_user:
        raise UserAlreadyExists(user_email=existing_user.email)

    hashed_password = hash_password(user_in.password)
    new_user = User(email=user_in.email, hashed_password=hashed_password)
    db_session.add(new_user)
    db_session.commit()
    db_session.refresh(new_user)
    return new_user
