from typing import Annotated

from fastapi import FastAPI, Path, Query

from schema import ItemCreate, ItemPublic

app = FastAPI()


@app.get("/")
def read_root():
    return {"message": "Hello, FastAPI!"}


@app.get("/items/{item_id}")
def get_item(
    item_id: Annotated[int, Path(ge=1)],
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
    q: Annotated[str | None, Query(min_length=3, max_length=50)] = None,
) -> dict:
    return {"item_id": item_id, "q": q, "limit": limit}


@app.post("/items", response_model=ItemPublic)
def create_item(item: ItemCreate):
    return {
        "id": 1,
        "name": item.name,
        "price": item.price,
        "description": item.description,
        "secret_memo": item.secret_memo,
    }
