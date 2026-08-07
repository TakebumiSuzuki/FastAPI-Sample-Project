from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from app.deps import CommonQueryParams, get_db_session
from app.schemas import ItemCreate, ItemPublic

router = APIRouter(prefix="/items", tags=["items"])


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


@router.get("/{item_id}")
def get_item(
    item_id: Annotated[int, Path(ge=1)],
    params: Annotated[CommonQueryParams, Depends()],
    db: Annotated[str, Depends(get_db_session)],
    q: Annotated[str | None, Query(min_length=3, max_length=50)] = None,
) -> dict:
    if item_id > 100:
        raise ItemNotFound(item_id)
    if item_id == 50:
        raise ItemOutOfStock(item_id)
    return {
        "item_id": item_id,
        "q": q,
        "limit": params.limit,
        "skip": params.skip,
        "db": db,
    }


@router.post("", response_model=ItemPublic, status_code=201)
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
