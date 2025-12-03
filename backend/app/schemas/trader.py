from datetime import datetime

from pydantic import BaseModel, Field


class TraderBase(BaseModel):
    address: str = Field(..., description="Unique trader address on Hyperliquid or other exchanges")


class TraderCreate(TraderBase):
    """Schema for creating or updating a trader."""


class TraderRead(TraderBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TraderListResponse(BaseModel):
    total: int
    items: list[TraderRead]


