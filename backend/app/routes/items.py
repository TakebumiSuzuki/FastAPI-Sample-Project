from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path
from sqlalchemy.orm import Session

from app.crud import item as crud
from app.deps import CommonQueryParams, get_db_session
from app.exceptions import ItemNameTaken, ItemNotFound
from app.models.item import Item
from app.schemas import ItemCreate, ItemPublic, ItemUpdate

router = APIRouter(prefix="/items", tags=["items"])


@router.get("/{item_id}", response_model=ItemPublic)
def get_item(
    item_id: Annotated[int, Path(ge=1)],
    db: Annotated[Session, Depends(get_db_session)],
) -> Item:
    item = crud.get_item_from_id(db=db, item_id=item_id)
    if item:
        return item
    else:
        raise ItemNotFound(item_id)


@router.get("", response_model=list[ItemPublic])
def get_items(
    db: Annotated[Session, Depends(get_db_session)],
    params: Annotated[CommonQueryParams, Depends()],
) -> Sequence[Item]:
    items = crud.get_items(db=db, skip=params.skip, limit=params.limit)
    return items


@router.post("", response_model=ItemPublic, status_code=201)
def create_item(
    db: Annotated[Session, Depends(get_db_session)],
    new_item: Annotated[ItemCreate, Body()],
) -> Item:
    if crud.get_item_by_name(db=db, item_name=new_item.name) is not None:
        raise ItemNameTaken(new_item.name)
    item = crud.create_item(db=db, item_in=new_item)
    return item


@router.put("/{item_id}", response_model=ItemPublic)
def update_item(
    db: Annotated[Session, Depends(get_db_session)],
    item_id: Annotated[int, Path()],
    update: Annotated[ItemUpdate, Body()],
) -> Item:
    item = crud.get_item_from_id(db=db, item_id=item_id)
    if item is None:
        raise ItemNotFound(item_id)
    new_item = crud.update_item(db=db, db_item=item, item_in=update)
    return new_item


@router.delete("/{item_id}", status_code=204)
def delete_item(
    db: Annotated[Session, Depends(get_db_session)],
    item_id: Annotated[int, Path()],
) -> None:
    item = crud.get_item_from_id(db=db, item_id=item_id)
    if item is None:
        raise ItemNotFound(item_id=item_id)
    crud.delete_item(db=db, db_item=item)
