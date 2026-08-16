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
