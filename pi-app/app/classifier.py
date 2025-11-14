from typing import Tuple

from PIL import Image


def dominant_colour(path) -> str:
    try:
        img = Image.open(path).convert("RGB").resize((32, 32))
        pixels = list(img.getdata())
        r = sum(p[0] for p in pixels) // len(pixels)
        g = sum(p[1] for p in pixels) // len(pixels)
        b = sum(p[2] for p in pixels) // len(pixels)
        if r < 40 and g < 40 and b < 40:
            return "Black"
        if r > 200 and g > 200 and b > 200:
            return "White"
        if b > r and b > g:
            return "Blue"
        if g > r and g > b:
            return "Green"
        if r > g and r > b:
            return "Red"
        return "Mixed"
    except Exception:
        return "Unknown"


def item_type_from_name(name: str) -> Tuple[str, str]:
    n = name.lower()
    for k in [
        "hoodie",
        "dress",
        "jeans",
        "tshirt",
        "tee",
        "shirt",
        "jacket",
        "coat",
        "skirt",
        "shorts",
        "trainers",
        "shoes",
    ]:
        if k in n:
            return k, "Medium"
    return "clothing", "Low"
