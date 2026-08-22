from functools import lru_cache

from pydantic import EmailStr
from pydantic_settings import BaseSettings, SettingsConfigDict


# インスタンス化のタイミングで、裏で python-dotenv が .env を読み込み、
# OS環境変数などとマージした上で、Pydantic による型変換とバリデーションが行われる
# env_file の値は cwd基準。値の優先順位は、
# ① インスタンス化時の引数（Settings(database_url="...") など）
# ② OSの環境変数（os.environ）
# ③ .env ファイルの値
# ④ クラス定義のデフォルト値（app_name = "FastAPI App" など）
class Settings(BaseSettings):
    app_name: str = "FastAPI App"
    admin_email: EmailStr
    items_per_user: int = 50
    database_url: str

    model_config = SettingsConfigDict(env_file=".env")


# API リクエストのたびに Settings() を呼ぶと、毎回インスタンス化をすることになり、
# その度に .env のパースやバリデーションが走ってしまう。キャッシュすることで
# 初回に作成した 1つのインスタンスをアプリ全体で使い回す（シングルトン化する）
# lru_cache でも、より新しい cache を使っても、どちらでも良い。
# 関数(callable)として定義しているので、テスト時には、
# Depends(get_settings) としてエンドポイントに注入できる。
# また、環境変数を差し替えて再読み込みしたい場合には、get_settings.cache_clear()
# を呼ぶことで簡単にキャッシュをリセット可能。
@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
