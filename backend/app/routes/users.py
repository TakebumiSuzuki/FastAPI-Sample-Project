from typing import Annotated

from fastapi import Body, Cookie, Depends, HTTPException, Response
from fastapi.routing import APIRouter
from sqlalchemy.orm import Session

from app.core.security import create_access_token, create_refresh_token
from app.crud import user as crud_user
from app.deps import get_db_session, get_user
from app.models import User
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
    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email},
    )
    refresh_token = create_refresh_token(
        data={"sub": str(user.id), "email": user.email},
    )
    crud_user.register_refresh_token(
        db_session=db_session,
        user_id=user.id,
        refresh_token=refresh_token,
    )

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        path="/users",
    )
    return {"access_token": access_token}


@router.post("/logout", status_code=204)
def logout_user(
    db_session: Annotated[Session, Depends(get_db_session)],
    response: Response,
    user: Annotated[User, Depends(get_user)],
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> None:
    # サーバーは Cookie を直接消せないため、同じ名前・path で期限切れ(Max-Age=0)の
    # Cookie を送り、ブラウザに上書き→即削除させる。path が違うと別物扱いで消えない。
    response.delete_cookie("refresh_token", path="/users")
    if refresh_token:
        crud_user.revoke_refresh_token(
            db_session=db_session, refresh_token=refresh_token
        )


@router.post("/refresh", status_code=200, response_model=Token)
def refresh_tokens(
    db_session: Annotated[Session, Depends(get_db_session)],
    response: Response,
    # | None がないと、422のエラーとして処理されるが、401のエラーとして
    # 処理したいので、一旦 Noneとして関数を実行させるようにしている。
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> dict[str, str]:
    new_access_token, new_refresh_token = crud_user.reissue_tokens(
        db_session=db_session,
        refresh_token=refresh_token,
    )
    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        path="/users",
    )
    return {"access_token": new_access_token}
