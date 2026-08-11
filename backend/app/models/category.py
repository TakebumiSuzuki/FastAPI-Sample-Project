from app.models.base import Base 
from sqlalchemy.orm import mapped_column, Mapped, relationship
from sqlalchemy import Integer, String


class Category(Base):
    __tablename__ = "categories"
    
    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    name: Mapped[str] = mapped_column(String(30))
    
    items: Mapped[list["Item"]] = relationship("Item", back_populates="category")
    