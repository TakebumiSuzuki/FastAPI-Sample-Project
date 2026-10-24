from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int]
    refresh_token: Mapped[str] = mapped_column(String(512))
    active: Mapped[bool] = mapped_column(default=True)
