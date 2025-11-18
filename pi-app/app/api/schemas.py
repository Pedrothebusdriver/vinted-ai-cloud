from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class DraftPhotoSchema(BaseModel):
    id: Optional[int] = None
    url: Optional[str] = None
    original_path: Optional[str] = None
    optimised_path: Optional[str] = None
    file_path: Optional[str] = None
    position: Optional[int] = None


class DraftSummarySchema(BaseModel):
    id: int
    title: str
    status: str = "draft"
    brand: Optional[str] = None
    size: Optional[str] = None
    colour: Optional[str] = None
    price_mid: Optional[float] = None
    updated_at: Optional[int] = None
    thumbnail_url: Optional[str] = None


class DraftResponseSchema(DraftSummarySchema):
    description: Optional[str] = None
    category_id: Optional[str] = None
    category_name: Optional[str] = None
    condition: Optional[str] = None
    price_low: Optional[float] = None
    price_high: Optional[float] = None
    selected_price: Optional[float] = None
    created_at: Optional[int] = None
    photos: List[DraftPhotoSchema] = Field(default_factory=list)
    prices: Dict[str, Optional[float]] = Field(default_factory=dict)


class DraftUpdatePayload(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    selected_price: Optional[float] = None
    price: Optional[float] = None
    category_id: Optional[str] = None
    category_name: Optional[str] = None

    class Config:
        allow_population_by_field_name = True
