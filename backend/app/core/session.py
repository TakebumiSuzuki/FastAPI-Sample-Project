# core/ の基準は「使用範囲の広さ」ではなく「アプリの起動時に一度だけ組み立てる土台」
# と考えると、このファイルを core の中に入れても良いと言うのが claude の意見
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings

engine = create_async_engine(
    get_settings().database_url,
    connect_args={"check_same_thread": False},
    echo=True,
)

SessionLocal = async_sessionmaker(
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)
