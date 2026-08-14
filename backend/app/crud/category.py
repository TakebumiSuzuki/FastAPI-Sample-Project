from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.category import Category


def get_categories(db: Session) -> Sequence[Category]:
    categories = db.execute(select(Category)).scalars().all()
    return categories
