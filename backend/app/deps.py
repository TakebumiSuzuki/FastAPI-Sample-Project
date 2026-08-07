from collections.abc import Generator
from typing import Annotated

from fastapi import Query


class CommonQueryParams:
    def __init__(
        self,
        skip: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1, le=100)] = 10,
    ):
        self.skip = skip
        self.limit = limit


def get_db_session() -> Generator[str]:
    print("--- [前処理] DBセッションを開きました ---")
    try:
        yield "fake_db_session_object"
    finally:
        print("--- [後片付け] DBセッションを閉じました ---")
