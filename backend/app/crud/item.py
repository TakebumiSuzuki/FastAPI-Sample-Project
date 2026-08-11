from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
from app.models.item import Item 
from app.schemas import ItemCreate, ItemUpdate 

def get_item_from_id(db: Session, item_id: int) -> Item | None:
    stmt = select(Item).where(Item.id == item_id).options(joinedload(Item.category))
    item = db.execute(stmt).scalar_one_or_none()
    return item

def get_item_by_name(db: Session, item_name: str) -> Item | None:
    stmt = select(Item).where(Item.name == item_name).options(joinedload(Item.category))
    item = db.execute(stmt).scalar_one_or_none()
    return item

def get_items(db: Session, skip: int = 0, limit: int = 10) -> list[Item]:
    stmt = select(Item).offset(skip).limit(limit).options(joinedload(Item.category))
    items = db.execute(stmt).scalars().all()
    return items

def create_item(db: Session, item_in: ItemCreate) -> Item:
    new_item = Item(**item_in.model_dump())
    db.add(new_item)
    db.commit()
    return new_item

def update_item(db: Session, db_item: Item, item_in: ItemUpdate) -> Item:
    for k, v in item_in.model_dump(exclude_unset=True).items():
        setattr(db_item, k, v)
    db.commit()
    return db_item

def delete_item(db: Session, db_item: Item) -> None:
    db.delete(db_item)
    db.commit()
    return
