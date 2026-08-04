from typing import Annotated

from fastapi import FastAPI, HTTPException, Path, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from schema import ItemCreate, ItemPublic

app = FastAPI()


class ItemNotFound(HTTPException):
    code = "item_not_found"

    def __init__(self, item_id: int):
        super().__init__(status_code=404, detail=f"Item {item_id} not found")
        self.details = {"item_id": item_id}


class ItemNameTaken(HTTPException):
    code = "item_name_taken"

    def __init__(self, name: str):
        super().__init__(status_code=409, detail=f"Item name '{name}' is already used")
        self.details = {"name": name}


class ItemOutOfStock(HTTPException):
    code = "item_out_of_stock"

    def __init__(self, item_id: int):
        super().__init__(status_code=400, detail=f"Item {item_id} is out of stock")
        self.details = {"item_id": item_id}


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": getattr(exc, "code", "http_error"),
                "message": exc.detail,
                "details": getattr(exc, "details", {}),
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "validation_error",
                "message": "入力内容を確認してください",
                # loc の先頭は "body" / "query" などの出所なので落とし、残りをつないで項目名にする
                "details": {
                    ".".join(str(part) for part in error["loc"][1:]): error["msg"]
                    for error in exc.errors()
                },
            }
        },
    )


@app.get("/")
def read_root():
    return {"message": "Hello, FastAPI!"}


@app.get("/items/{item_id}")
def get_item(
    item_id: Annotated[int, Path(ge=1)],
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
    q: Annotated[str | None, Query(min_length=3, max_length=50)] = None,
) -> dict:
    if item_id > 100:
        raise ItemNotFound(item_id)
    if item_id == 50:
        raise ItemOutOfStock(item_id)
    return {"item_id": item_id, "q": q, "limit": limit}


@app.post("/items", response_model=ItemPublic, status_code=201)
def create_item(item: ItemCreate):
    if item.name == "りんご":
        raise ItemNameTaken(item.name)
    return {
        "id": 1,
        "name": item.name,
        "price": item.price,
        "description": item.description,
        "secret_memo": item.secret_memo,
    }
