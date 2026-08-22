from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.category import Category


def get_categories(db_session: Session) -> Sequence[Category]:
    categories = db_session.execute(select(Category)).scalars().all()
    return categories
