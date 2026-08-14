from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Depends, Body
from sqlalchemy.orm import Session

from app.crud.category import get_categories as crud_get_categories
from app.deps import get_db_session
from app.models.category import Category
from app.schemas import CategoryPublic, CategoryCreate

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=list[CategoryPublic])
def get_categories(
    db: Annotated[Session, Depends(get_db_session)],
) -> Sequence[Category]:
    categories = crud_get_categories(db=db)
    return categories


@router.post("", response_model=CategoryPublic, status_code=201)
def create_category(
    new_category: Annotated[CategoryCreate, Body()],
    db: Annotated[Session, Depends(get_db_session)],
):
    category = Category(name=new_category.name)
    db.add(category)
    db.commit()
    return category
