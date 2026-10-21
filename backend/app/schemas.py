from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

# EmailStr は、デフォルトで前後の半角スペースおよび全角スペースを自動的に除去（トリム）します。


class ItemBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=50)
    price: float = Field(gt=0)
    sale_price: float | None = Field(default=None, gt=0)
    description: str | None = Field(default=None, max_length=5000)
    category_id: int = Field(gt=0)

    @model_validator(mode="after")
    def check_sale_price(self):
        if self.sale_price is not None and self.sale_price >= self.price:
            raise ValueError("sale_price must be lower than price")
        return self


class ItemCreate(ItemBase):
    secret_memo: str | None = Field(default=None, max_length=1000)


class ItemPublic(ItemBase):
    id: int
    category: "CategoryPublic"
    model_config = ConfigDict(from_attributes=True)


class ItemUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=50)
    price: float | None = Field(default=None, gt=0)
    sale_price: float | None = Field(default=None, gt=0)
    description: str | None = Field(default=None, max_length=5000)
    category_id: int | None = Field(default=None)

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


class CategoryBase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=3, max_length=30)


class CategoryPublic(CategoryBase):
    model_config = ConfigDict(from_attributes=True)
    id: int = Field(ge=1)


class CategoryCreate(CategoryBase):
    pass


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(max_length=255, min_length=8)
    model_config = ConfigDict(extra="forbid")

    @field_validator("password", mode="after")
    @classmethod
    def check_password(cls, v: str) -> str:
        if not any(char.isdigit() for char in v):
            raise ValueError("Password must contain at least one digit")
        if not any(char.isupper() for char in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(char.islower() for char in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(char in "!@#$%^&*()_+-=[]{}|;:,.<>?" for char in v):
            raise ValueError("Password must contain at least one special character")
        return v


class UserPublic(BaseModel):
    id: int
    email: EmailStr
    model_config = ConfigDict(from_attributes=True)


# 送る直前（サーバーからクライアントへレスポンスを返す時）に使う
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserLogin(BaseModel):
    email: EmailStr
    password: str
    model_config = ConfigDict(extra="forbid")
