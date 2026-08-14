from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from app.crud.item import create_item as crud_create_item
from app.crud.item import delete_item as crud_delete_item
from app.crud.item import get_item_by_name, get_item_from_id
from app.crud.item import get_items as crud_get_items
from app.crud.item import update_item as crud_update_item
from app.deps import CommonQueryParams, get_db_session
from app.models.item import Item
from app.schemas import ItemCreate, ItemPublic, ItemUpdate

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


@router.get("/{item_id}", response_model=ItemPublic)
def get_item(
    item_id: Annotated[int, Path(ge=1)],
    db: Annotated[Session, Depends(get_db_session)],
) -> Item:
    item = get_item_from_id(db=db, item_id=item_id)
    if item:
        return item
    else:
        raise ItemNotFound(item_id)


@router.get("", response_model=list[ItemPublic])
def get_items(
    db: Annotated[Session, Depends(get_db_session)],
    params: Annotated[CommonQueryParams, Depends()],
) -> list[Item]:
    items = crud_get_items(db=db, skip=params.skip, limit=params.limit)
    return items


@router.post("", response_model=ItemPublic, status_code=201)
def create_item(
    db: Annotated[Session, Depends(get_db_session)],
    new_item: Annotated[ItemCreate, Body()],
) -> Item:
    if get_item_by_name(db=db, item_name=new_item.name) is not None:
        raise ItemNameTaken(new_item.name)
    new_item = crud_create_item(db=db, item_in=new_item)
    return new_item


@router.put("/{item_id}", response_model=ItemPublic)
def update_item(
    db: Annotated[Session, Depends(get_db_session)],
    item_id: Annotated[int, Path()],
    update: Annotated[ItemUpdate, Body()],
) -> Item:
    item = get_item_from_id(db=db, item_id=item_id)
    if item is None:
        raise ItemNotFound(item_id)
    new_item = crud_update_item(db=db, db_item=item, item_in=update)
    return new_item


@router.delete("/{item_id}", status_code=204)
def delete_item(
    db: Annotated[Session, Depends(get_db_session)], item_id: Annotated[int, Path()]
) -> None:
    item = get_item_from_id(db=db, item_id=item_id)
    if item is None:
        raise ItemNotFound(item_id=item_id)
    crud_delete_item(db=db, db_item=item)
