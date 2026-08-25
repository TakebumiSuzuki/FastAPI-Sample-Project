# 【設計についてのメモ】
# 1. アプリケーションファクトリーパターン（create_app関数内でappを生成して返す設計）は
# Flask等でテスト容易性の向上目的によく使われるが、FastAPIでは、 Depends や
# dependency_overrides があるため、本ファイルのように直接 app = FastAPI() と定義するのが一般的
# 2. 実務やFastAPI公式推奨では、main.py を app/main.py に配置し、
# アプリケーションコード全体を app/ ディレクトリ内に集約させる構成が多く用いられる。

from fastapi import FastAPI

from app.core.config import get_settings
from app.core.error_handlers import register_error_handlers
from app.routes.categories import router as categories_router
from app.routes.items import router as items_router

app = FastAPI()

register_error_handlers(app)


@app.get("/")
def read_root():
    settings = get_settings()
    return {"message": "Hello, FastAPI!", "app_name": settings.app_name}


app.include_router(items_router)
app.include_router(categories_router)
