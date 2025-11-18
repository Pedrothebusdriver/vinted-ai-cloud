import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from core import category_suggester


def test_suggest_categories_ranks_keywords():
    results = category_suggester.suggest_categories(
        hint_text="Vintage Nike hoodie",
        ocr_text="",
        filename="nike_hoodie.jpg",
        limit=3,
    )
    assert results, "expected at least one category"
    assert results[0].id == "mens_hoodies"
    assert results[0].score >= results[1].score if len(results) > 1 else True


def test_suggest_categories_uses_filename_when_text_missing():
    results = category_suggester.suggest_categories(
        hint_text="",
        ocr_text="",
        filename="summer_dress.png",
    )
    assert results
    assert any(cat.id == "womens_dresses" for cat in results)
