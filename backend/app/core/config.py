from functools import lru_cache

from pydantic import EmailStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "FastAPI App"
    admin_email: EmailStr
    items_per_user: int = 50
    database_url: str

    model_config = SettingsConfigDict(env_file=".env")


# lru_cache の使用が推奨されるのは主にテストの都合。
# Depends(get_settings) としてエンドポイントに注入しできるから。
@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
