from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RefreshToken(Base):
    # user_id カラムは冗長に見えるが、パスワード変更時に全端末をログアウトさせる時や
    # ログイン中の端末を一覧表示する、時に必要となる。
    __tablename__ = "refresh_tokens"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int]
    refresh_token: Mapped[str] = mapped_column(String(512))
    active: Mapped[bool] = mapped_column(default=True)
