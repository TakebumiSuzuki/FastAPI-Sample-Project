from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from app.crud import category as crud
from app.deps import get_db_session
from app.models.category import Category
from app.schemas import CategoryCreate, CategoryPublic

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=list[CategoryPublic])
def get_categories(
    db: Annotated[Session, Depends(get_db_session)],
) -> Sequence[Category]:
    categories = crud.get_categories(db=db)
    return categories


@router.post("", response_model=CategoryPublic, status_code=201)
def create_category(
    new_category: Annotated[CategoryCreate, Body()],
    db: Annotated[Session, Depends(get_db_session)],
) -> Category:
    category = Category(name=new_category.name)
    db.add(category)
    db.commit()
    return category
