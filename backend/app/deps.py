from collections.abc import Generator
from typing import Annotated

from app.db.session import SessionLocal

from fastapi import Query
from sqlalchemy.orm import Session


class CommonQueryParams:
    def __init__(
        self,
        skip: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1, le=100)] = 10,
    ):
        self.skip = skip
        self.limit = limit


def get_db_session() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        
