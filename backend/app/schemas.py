from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import List
from datetime import datetime

class LoginInput(BaseModel):
    username: str
    password: str

class TokenOutput(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str

class ProductInput(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    category: str = Field(default="General", max_length=100)
    price: float = Field(gt=0)
    stock: int = Field(ge=0)

    @field_validator("name", "category")
    @classmethod
    def strip_and_validate(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Field cannot be empty or whitespace.")
        return s

class ProductOutput(ProductInput):
    id: int
    model_config = ConfigDict(from_attributes=True)

class SaleItemInput(BaseModel):
    product_id: int
    quantity: int = Field(gt=0)

class SaleInput(BaseModel):
    items: List[SaleItemInput] = Field(min_length=1)

class OrderItemOutput(BaseModel):
    id: int
    product_id: int
    product_name: str
    quantity: int
    unit_price: float
    line_total: float
    model_config = ConfigDict(from_attributes=True)

class OrderOutput(BaseModel):
    id: int
    created_at: datetime
    total: float
    items: List[OrderItemOutput]
    model_config = ConfigDict(from_attributes=True)
