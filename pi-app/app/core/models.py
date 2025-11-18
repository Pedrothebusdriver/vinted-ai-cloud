from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class DraftPhoto(BaseModel):
    path: str
    original_path: Optional[str] = None
    optimised_path: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    is_label: bool = False
    source_url: Optional[str] = None


class PriceEstimate(BaseModel):
    low: Optional[float] = None
    mid: Optional[float] = None
    high: Optional[float] = None
    examples: List[Dict[str, Any]] = Field(default_factory=list)

    @property
    def has_prices(self) -> bool:
        return any(value is not None for value in (self.low, self.mid, self.high))

    def as_response(self) -> Dict[str, Optional[float]]:
        return {
            "value": self.mid,
            "p25": self.low,
            "p75": self.high,
        }


class CategorySuggestion(BaseModel):
    id: str
    name: str
    score: float
    keywords: List[str] = Field(default_factory=list)


class Draft(BaseModel):
    id: Optional[int] = None
    title: Optional[str] = None
    description: Optional[str] = None
    brand: Optional[str] = None
    size: Optional[str] = None
    colour: Optional[str] = None
    category_id: Optional[str] = None
    category_name: Optional[str] = None
    condition: str = "Good"
    status: str = "draft"
    label_text: Optional[str] = None
    price: PriceEstimate = Field(default_factory=PriceEstimate)
    photos: List[DraftPhoto] = Field(default_factory=list)
    metadata: Dict[str, str] = Field(default_factory=dict)
