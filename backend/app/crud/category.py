from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category


async def get_categories(db_session: AsyncSession) -> Sequence[Category]:
    stmt = select(Category).order_by(Category.id)
    categories = (await db_session.execute(stmt)).scalars().all()
    return categories
