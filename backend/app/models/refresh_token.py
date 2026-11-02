from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


# ホワイトリストとも言える。過去に発行されたリフレッシュトークンが
# 履歴として全てこのテーブルに残り、無効なものは active=False になる。
class RefreshToken(Base):
    # user_id カラムは冗長に見えるが、パスワード変更時に全端末をログアウト
    # させる時やログイン中の端末を一覧表示する、時に必要となる。
    # つまり、PC、スマートフォン、異なるブラウザからのログインなどにより、
    # 1人のユーザーに対して複数のレコードが存在する可能性がある。
    # で、さらにアクセス元を別カラムに保存するという実装も考えられる。
    __tablename__ = "refresh_tokens"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int]
    refresh_token: Mapped[str] = mapped_column(String(512))
    active: Mapped[bool] = mapped_column(default=True)

    # このままの実装だと、期限切れのリフレッシュトークンが、active=True
    # の状態で溜まり続けることになる。よって、expires_at　のような
    # カラムを作り、バッチ処理で、定期的に期限切れのものを active=False
    # にするような仕組みを作れば、よりすっきりする。
