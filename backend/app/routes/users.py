from typing import Annotated

from fastapi import Body, Depends, HTTPException, Response
from fastapi.routing import APIRouter
from sqlalchemy.orm import Session

from app.core.security import create_access_token, create_refresh_token
from app.crud import user as crud_user
from app.deps import get_db_session
from app.schemas import Token, UserCreate, UserLogin, UserPublic

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


@router.post("/login", response_model=Token)
def login_user(
    db_session: Annotated[Session, Depends(get_db_session)],
    login_in: Annotated[UserLogin, Body()],
    response: Response,
) -> dict:
    # 以下は DB に Login情報を保存する処理ではなく「メールアドレスで検索してパスワードを
    # 照合する処理なので、引数を個別に渡す形がプロジェクト全体と一貫しています。
    user = crud_user.authenticate_user(
        db_session=db_session,
        email=login_in.email,
        password=login_in.password,
    )
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password",
        )
    # subは文字列にする必要がある。
    access_token = create_access_token(data={"sub": str(user.id), "email": user.email})
    refresh_token = create_refresh_token(
        data={"sub": str(user.id), "email": user.email}
    )
    response.set_cookie(key="refresh_token", value=refresh_token, httponly=True)
    return {"access_token": access_token}


# /users/refresh

# /users/logout
