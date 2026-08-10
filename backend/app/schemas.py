from pydantic import BaseModel, ConfigDict, Field, model_validator


class ItemBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=50)
    price: float = Field(gt=0)
    sale_price: float | None = Field(default=None, gt=0)
    description: str | None = Field(default=None, max_length=5000)

    @model_validator(mode="after")
    def check_sale_price(self):
        if self.sale_price is not None and self.sale_price >= self.price:
            raise ValueError("sale_price must be lower than price")
        return self


class ItemCreate(ItemBase):
    secret_memo: str | None = Field(default=None, max_length=1000)


class ItemPublic(ItemBase):
    id: int
    
    model_config = ConfigDict(from_attributes=True)
    



class ItemUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=50)
    price: float | None = Field(default=None, gt=0)
    sale_price: float | None = Field(default=None, gt=0)
    description: str | None = Field(default=None, max_length=5000)

    @model_validator(mode="after")
    def check_no_data(self):
        if not self.model_fields_set:
            raise ValueError("no fields to update")
        return self

    @model_validator(mode="after")
    def check_sale_price(self):
        if (
            self.price is not None
            and self.sale_price is not None
            and self.sale_price >= self.price
        ):
            raise ValueError("sale_price must be lower than price")
        return self
