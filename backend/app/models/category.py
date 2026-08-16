from typing import TYPE_CHECKING

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.item import Item


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    name: Mapped[str] = mapped_column(String(30))

    items: Mapped[list["Item"]] = relationship("Item", back_populates="category")
