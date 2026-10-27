from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from app.crud import category as crud
from app.deps import get_db_session, get_user
from app.models import Category
from app.schemas import CategoryCreate, CategoryPublic

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=list[CategoryPublic])
def get_categories(
    db_session: Annotated[Session, Depends(get_db_session)],
) -> Sequence[Category]:
    categories = crud.get_categories(db_session=db_session)
    return categories


@router.post(
    "", response_model=CategoryPublic, status_code=201, dependencies=[Depends(get_user)]
)
def create_category(
    new_category: Annotated[CategoryCreate, Body()],
    db_session: Annotated[Session, Depends(get_db_session)],
) -> Category:
    # 以下を、category = Category(**new_category.model_dump()) と書いても良い
    category = Category(name=new_category.name)
    db_session.add(category)
    db_session.commit()
    return category
