from sqlalchemy import Boolean, Integer, String, true
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    # saltの働きにより、パスワードが同じでも必ず一意の文字列になる。
    # また、ハッシュ値の前方にアルゴリズムや、salt の文字列が加えられる。
    hashed_password: Mapped[str] = mapped_column(String(128))
    is_active: Mapped[bool] = mapped_column(
        # Postgres の場合でも true() を使うというのは同じ。
        # そもそも、server_default=true()を入れているのは、データが入った
        # 状態でカラムを新設して、マイグレーションを行った時のエラーを防ぐため。
        Boolean(),
        default=True,
        server_default=true(),
    )
