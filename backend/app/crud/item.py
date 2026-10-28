from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.item import Item
from app.schemas import ItemCreate, ItemUpdate


async def get_item_from_id(db_session: AsyncSession, item_id: int) -> Item | None:
    stmt = select(Item).where(Item.id == item_id).options(joinedload(Item.category))
    item = (await db_session.execute(stmt)).scalar_one_or_none()
    return item


async def get_item_by_name(db_session: AsyncSession, item_name: str) -> Item | None:
    stmt = select(Item).where(Item.name == item_name).options(joinedload(Item.category))
    item = (await db_session.execute(stmt)).scalar_one_or_none()
    return item


async def get_items(
    db_session: AsyncSession, skip: int = 0, limit: int = 10
) -> Sequence[Item]:
    stmt = (
        select(Item)
        .order_by(Item.id)
        .offset(skip)
        .limit(limit)
        .options(joinedload(Item.category))
    )
    items = (await db_session.execute(stmt)).scalars().all()
    return items


async def create_item(db_session: AsyncSession, item_in: ItemCreate) -> Item:
    # model_dump()は Python 辞書に変換、model_dump_json() は JSON 文字列に変換
    new_item = Item(**item_in.model_dump())
    db_session.add(new_item)
    await db_session.commit()
    await db_session.refresh(new_item, ["category"])
    return new_item


async def update_item(
    db_session: AsyncSession, db_item: Item, item_in: ItemUpdate
) -> Item:
    for k, v in item_in.model_dump(exclude_unset=True).items():
        setattr(db_item, k, v)
    await db_session.commit()
    await db_session.refresh(db_item)
    return db_item


async def delete_item(db_session: AsyncSession, db_item: Item) -> None:
    # 関連データの道連れ削除（カスケード）の対象を調べるために DB へ SELECT が走ることがあるため、AsyncSession.delete() は awaitが必須になっています
    await db_session.delete(db_item)
    await db_session.commit()
