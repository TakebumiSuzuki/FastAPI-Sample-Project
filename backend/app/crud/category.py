from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.category import Category


def get_categories(db_session: Session) -> Sequence[Category]:
    stmt = select(Category).order_by(Category.id)
    categories = db_session.execute(stmt).scalars().all()
    return categories
