import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Union


@dataclass
class Prediction:
    colour: str
    category: str
    brand: str
    condition: str
    price_range: str
    price_gbp: Optional[float]
    size: Optional[str] = None


BRAND_KEYWORDS: Dict[str, str] = {
    "nike": "Nike",
    "adidas": "Adidas",
    "levis": "Levi's",
    "levi": "Levi's",
    "patagonia": "Patagonia",
    "zara": "Zara",
    "northface": "The North Face",
    "north_face": "The North Face",
}

CATEGORY_KEYWORDS: Dict[str, str] = {
    "sneaker": "Sneakers",
    "sneakers": "Sneakers",
    "shoe": "Shoes",
    "jacket": "Jacket",
    "coat": "Coat",
    "dress": "Dress",
    "bag": "Bag",
    "hoodie": "Hoodie",
}

COLOUR_KEYWORDS: Dict[str, str] = {
    "red": "Red",
    "blue": "Blue",
    "green": "Green",
    "white": "White",
    "black": "Black",
    "brown": "Brown",
    "tan": "Tan",
}

CONDITION_KEYWORDS: Dict[str, str] = {
    "new": "New",
    "nwot": "New without tags",
    "nwt": "New with tags",
    "vintage": "Vintage",
    "worn": "Used - worn",
    "used": "Used",
    "gently": "Used - good",
}


def _tokenise_path(path: str) -> List[str]:
    tokens = re.split(r"[^a-z0-9]+", path.lower())
    return [token for token in tokens if token]


def _find_match(tokens: Iterable[str], keyword_map: Dict[str, str]) -> str:
    for token in tokens:
        if token in keyword_map:
            return keyword_map[token]
    return "unknown"


def _infer_price_range(tokens: Iterable[str]) -> str:
    # Use the first integer we find as an anchor for a simple +/- range.
    for token in tokens:
        if token.isdigit():
            amount = int(token)
            lower = max(0, amount - 10)
            upper = amount + 10
            return f"£{lower}-£{upper}"
    return "£0-£0"


def _infer_price_mid(tokens: Iterable[str]) -> Optional[float]:
    for token in tokens:
        if token.isdigit():
            amount = int(token)
            return float(amount)
    return None


class BaselineInferencer:
    """String-based placeholder inference that can be swapped for a real model."""

    def predict(self, example_or_path: Union[Path, str]) -> Prediction:
        image_path = example_or_path
        if hasattr(example_or_path, "image_path"):
            image_path = getattr(example_or_path, "image_path")
        tokens = _tokenise_path(Path(str(image_path)).name)

        colour = _find_match(tokens, COLOUR_KEYWORDS)
        category = _find_match(tokens, CATEGORY_KEYWORDS)
        brand = _find_match(tokens, BRAND_KEYWORDS)
        condition = _find_match(tokens, CONDITION_KEYWORDS)
        price_range = _infer_price_range(tokens)
        price_mid = _infer_price_mid(tokens)

        return Prediction(
            colour=colour,
            category=category,
            brand=brand,
            condition=condition,
            price_range=price_range,
            price_gbp=price_mid,
            size=None,
        )
