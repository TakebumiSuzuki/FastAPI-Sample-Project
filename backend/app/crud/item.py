from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.item import Item
from app.schemas import ItemCreate, ItemUpdate


def get_item_from_id(db_session: Session, item_id: int) -> Item | None:
    stmt = select(Item).where(Item.id == item_id).options(joinedload(Item.category))
    item = db_session.execute(stmt).scalar_one_or_none()
    return item


def get_item_by_name(db_session: Session, item_name: str) -> Item | None:
    stmt = select(Item).where(Item.name == item_name).options(joinedload(Item.category))
    item = db_session.execute(stmt).scalar_one_or_none()
    return item


def get_items(db_session: Session, skip: int = 0, limit: int = 10) -> Sequence[Item]:
    stmt = select(Item).offset(skip).limit(limit).options(joinedload(Item.category))
    items = db_session.execute(stmt).scalars().all()
    return items


def create_item(db_session: Session, item_in: ItemCreate) -> Item:
    new_item = Item(**item_in.model_dump())
    db_session.add(new_item)
    db_session.commit()
    return new_item


def update_item(db_session: Session, db_item: Item, item_in: ItemUpdate) -> Item:
    for k, v in item_in.model_dump(exclude_unset=True).items():
        setattr(db_item, k, v)
    db_session.commit()
    return db_item


def delete_item(db_session: Session, db_item: Item) -> None:
    db_session.delete(db_item)
    db_session.commit()
