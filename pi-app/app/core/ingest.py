from __future__ import annotations

import asyncio
import logging
import shutil
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

import time

from app import compliance, events
from app.core import category_suggester
from app.core.models import CategorySuggestion, Draft, DraftPhoto
from app.core.pricing import PricingService
from app.ocr import OCR

logger = logging.getLogger(__name__)
_NORMALIZED_TEXT_KEYS = {"brand", "size", "colour", "title", "term", "condition"}
_NESTED_METADATA_KEYS = {"vinted"}


class DraftRejected(Exception):
    """Raised when a draft cannot be produced (e.g. all photos rejected)."""

    def __init__(self, reasons: Iterable[str]) -> None:
        self.reasons = [r for r in reasons if r] or ["non_compliant"]
        super().__init__(", ".join(self.reasons))


@dataclass(frozen=True)
class IngestPaths:
    converted_root: Path
    thumbs_root: Path
    placeholder_thumb: Optional[Path] = None


@dataclass
class ProcessedPhoto:
    original: Path
    optimised: Path
    thumb: Optional[Path] = None


BrandDetector = Callable[[str], Tuple[Optional[str], str, Optional[str], str]]
ItemTypeDetector = Callable[[str], Tuple[str, str]]
ColourDetector = Callable[[Path], str]
LabelHashFunc = Callable[[str], str]
LearnedLookup = Callable[[str], Optional[Tuple[Optional[str], Optional[str]]]]
TitleBuilder = Callable[[Optional[str], str, str, Optional[str]], str]
CategoryFunc = Callable[..., List[CategorySuggestion]]
ThumbMaker = Callable[[Path, Path], None]
JpegConverter = Callable[[Path, Path], bool]
PreprocessFunc = Callable[[Path], Path]


class IngestService:
    """Encapsulates the ingest flow shared by legacy and new Draft APIs."""

    def __init__(
        self,
        *,
        ocr: OCR,
        pricing_service: PricingService,
        paths: IngestPaths,
        to_jpeg: JpegConverter,
        make_thumb: ThumbMaker,
        preprocess_for_ocr: PreprocessFunc,
        detect_brand_size: BrandDetector,
        label_hash_fn: LabelHashFunc,
        dominant_colour: ColourDetector,
        item_type_from_name: ItemTypeDetector,
        make_listing_title: TitleBuilder,
        learned_lookup: Optional[LearnedLookup] = None,
        category_helper: Optional[CategoryFunc] = None,
        convert_semaphore: Optional[asyncio.Semaphore] = None,
        ocr_max_attempts: int = 3,
        ocr_retry_delay: float = 0.2,
        compliance_checker: Callable[[Path], Tuple[bool, str]] = compliance.check_image,
    ) -> None:
        self._ocr = ocr
        self._pricing = pricing_service
        self._paths = paths
        self._to_jpeg = to_jpeg
        self._make_thumb = make_thumb
        self._preprocess_for_ocr = preprocess_for_ocr
        self._detect_brand_size = detect_brand_size
        self._label_hash = label_hash_fn
        self._colour_detector = dominant_colour
        self._item_detector = item_type_from_name
        self._title_builder = make_listing_title
        self._learned_lookup = learned_lookup
        self._category_helper = category_helper or category_suggester.suggest_categories
        self._sem = convert_semaphore or asyncio.Semaphore(1)
        self._ocr_max_attempts = max(1, ocr_max_attempts)
        self._ocr_retry_delay = max(0.0, ocr_retry_delay)
        self._compliance_checker = compliance_checker

    async def build_draft(
        self,
        *,
        item_id: int,
        filepaths: Sequence[Path],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Draft:
        """Return a Draft populated with best-effort attributes."""

        if not filepaths:
            raise DraftRejected(["no_photos"])
        meta = _normalize_metadata(metadata)
        converted = await self._convert_images(item_id, filepaths)
        allowed = self._filter_compliant(item_id, converted)
        if not allowed:
            self._log_event("photos_rejected", level="warning", item_id=item_id)
            raise DraftRejected(["non_compliant"])

        label_text, label_hash = self._read_label_text(item_id, allowed)
        brand, brand_conf, size, size_conf = self._detect_from_sources(
            label_text=label_text,
            filepaths=filepaths,
            metadata=meta,
        )
        colour = _detect_colour_from_photos(self._colour_detector, allowed)
        name_hint = filepaths[0].name if filepaths else "clothing"
        item_type, item_conf = self._item_detector(name_hint)
        meta_vinted = (meta.get("vinted") or {}) if isinstance(meta, dict) else {}
        if (not item_type or item_type == "clothing") and (
            meta_vinted.get("title") or meta.get("title")
        ):
            derived, derived_conf = self._item_detector(
                meta_vinted.get("title") or meta.get("title") or name_hint
            )
            if derived:
                item_type, item_conf = derived, derived_conf

        categories = self._category_helper(
            hint_text=meta_vinted.get("title") or meta.get("title"),
            ocr_text=label_text,
            filename=name_hint,
        )
        best_category = categories[0] if categories else None

        price = await self._pricing.suggest_price(
            brand=brand,
            category=(best_category.name if best_category else item_type),
            size=size,
            condition="Good",
        )
        title = self._title_builder(brand, item_type, colour, size)

        draft = Draft(
            id=item_id,
            title=title,
            brand=brand,
            size=size,
            colour=colour,
            category_id=best_category.id if best_category else None,
            category_name=best_category.name if best_category else None,
            condition="Good",
            status="draft",
            label_text=label_text or "",
            price=price,
        )
        draft.metadata = {
            "brand_confidence": brand_conf,
            "size_confidence": size_conf,
            "item_confidence": item_conf,
            "label_hash": label_hash or "",
            "category_suggestions": [c.dict() for c in categories],
            "raw_metadata": meta,
            "item_type": item_type,
        }
        draft.photos = [
            DraftPhoto(
                path=str(photo.optimised),
                original_path=str(photo.original),
                optimised_path=str(photo.optimised),
                is_label=False,
            )
            for photo in allowed
        ]
        return draft

    def _log_event(
        self,
        event: str,
        *,
        level: str = "info",
        item_id: Optional[int] = None,
        **extra: Any,
    ) -> None:
        """Structured logging helper for ingest events."""
        payload = dict(extra)
        if item_id is not None:
            payload["item_id"] = item_id
        log_fn = getattr(logger, level, logger.info)
        log_fn(event, **payload)

    async def _convert_images(
        self,
        item_id: int,
        filepaths: Sequence[Path],
    ) -> List[ProcessedPhoto]:
        """
        Convert uploaded files into optimised JPEGs plus thumbnails.

        Heavy work is serialized via a semaphore so we do not overwhelm the Pi.
        """
        results: List[ProcessedPhoto] = []
        out_dir = self._paths.converted_root / f"item-{item_id}"
        out_dir.mkdir(parents=True, exist_ok=True)
        async with self._sem:
            for src in filepaths:
                dst = out_dir / Path(src.name).with_suffix(".jpg").name
                ok = await asyncio.to_thread(self._to_jpeg, src, dst)
                thumb = self._paths.thumbs_root / f"{dst.stem}.jpg"
                if ok:
                    await asyncio.to_thread(self._make_thumb, dst, thumb)
                    results.append(ProcessedPhoto(original=src, optimised=dst, thumb=thumb))
                else:
                    self._copy_placeholder_thumb(thumb)
                    self._log_event(
                        "convert_failed",
                        level="warning",
                        item_id=item_id,
                        source=str(src),
                    )
        return results

    def _filter_compliant(self, item_id: int, photos: Sequence[ProcessedPhoto]) -> List[ProcessedPhoto]:
        """
        Run compliance checks on each converted photo and drop rejected files.

        Rejections are tracked so callers can surface meaningful error messages.
        """
        allowed: List[ProcessedPhoto] = []
        rejected: List[str] = []
        for photo in photos:
            ok, reason = self._compliance_checker(photo.optimised)
            if ok:
                allowed.append(photo)
            else:
                rejected.append(reason)
                self._cleanup_photo(photo)
                self._log_event(
                    "photo_rejected",
                    level="warning",
                    item_id=item_id,
                    reason=reason,
                    photo=str(photo.optimised),
                )
        if not allowed:
            self._log_event(
                "all_photos_rejected",
                level="warning",
                item_id=item_id,
                reasons="; ".join(rejected) if rejected else None,
            )
            raise DraftRejected(rejected or ["no_valid_photos"])
        return allowed

    def _cleanup_photo(self, photo: ProcessedPhoto) -> None:
        with suppress(FileNotFoundError):
            photo.optimised.unlink()
        if photo.thumb:
            with suppress(FileNotFoundError):
                photo.thumb.unlink()

    def _copy_placeholder_thumb(self, thumb: Path) -> None:
        """Create a placeholder thumbnail when conversion fails."""
        if not self._paths.placeholder_thumb:
            return
        try:
            thumb.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(self._paths.placeholder_thumb, thumb)
        except Exception as exc:  # pragma: no cover - best effort logging
            logger.debug("thumb_placeholder_failed", error=str(exc))

    def _read_label_text(self, item_id: int, photos: Sequence[ProcessedPhoto]) -> Tuple[str, Optional[str]]:
        """Read OCR text from the best available photo and compute label hash."""
        best_score, best_text = -1, ""
        for photo in photos:
            prep = self._preprocess_for_ocr(photo.optimised)
            text = self._run_ocr_with_retry(item_id, prep)
            score = sum(ch.isalnum() for ch in text)
            if score > best_score:
                best_score, best_text = score, text
        label_hash = self._label_hash(best_text) if best_text else None
        return best_text, label_hash

    def _run_ocr_with_retry(self, item_id: int, img_path: Path) -> str:
        """Call OCR with retries/backoff, logging failures along the way."""
        last_error = ""
        for attempt in range(1, self._ocr_max_attempts + 1):
            try:
                return self._ocr.read_text(img_path)
            except Exception as exc:
                last_error = str(exc)
                self._log_event(
                    "ocr_attempt_failed",
                    level="warning",
                    item_id=item_id,
                    attempt=attempt,
                    error=last_error,
                )
                events.record_event(
                    "ocr_attempt_failed",
                    {"item_id": item_id, "attempt": attempt, "error": last_error},
                )
                if attempt < self._ocr_max_attempts and self._ocr_retry_delay:
                    time.sleep(self._ocr_retry_delay)
        self._log_event(
            "ocr_unrecoverable",
            level="error",
            item_id=item_id,
            attempts=self._ocr_max_attempts,
            error=last_error or "unknown_error",
        )
        events.record_event(
            "ocr_unrecoverable",
            {"item_id": item_id, "attempts": self._ocr_max_attempts, "error": last_error},
        )
        return ""

    def _detect_from_sources(
        self,
        *,
        label_text: str,
        filepaths: Sequence[Path],
        metadata: Dict[str, Any],
    ) -> Tuple[Optional[str], str, Optional[str], str]:
        """
        Combine OCR, learned labels, and metadata slugs to guess brand + size.

        Returns both the detected values and confidence labels to store in the DB.
        """
        meta_vinted = (metadata.get("vinted") or {}) if isinstance(metadata, dict) else {}
        brand = size = None
        brand_conf = size_conf = "Low"
        label_hash = self._label_hash(label_text) if label_text else None
        if label_hash and self._learned_lookup:
            learned = self._learned_lookup(label_hash)
            if learned:
                brand, size = learned
                if brand:
                    brand_conf = "High"
                if size:
                    size_conf = "High"
        if not (brand and size):
            detected = self._detect_brand_size(label_text)
            dbrand, dbconf, dsize, dsconf = detected
            if not brand and dbrand:
                brand, brand_conf = dbrand, dbconf
            if not size and dsize:
                size, size_conf = dsize, dsconf

        meta_brand = (metadata.get("brand") or meta_vinted.get("brand") or "").strip()
        meta_size = (metadata.get("size") or meta_vinted.get("size") or "").strip()
        if (not brand or not brand.strip()) and meta_brand:
            brand, brand_conf = meta_brand, "Meta"
        if (not size or not size.strip()) and meta_size:
            size, size_conf = meta_size, "Meta"

        if (not brand or not brand.strip()) or (not size or not size.strip()):
            slug_sources: List[str] = [
                str(meta_vinted.get("title") or ""),
                str(meta_vinted.get("id") or ""),
                str(metadata.get("title") or ""),
                str(metadata.get("term") or ""),
            ]
            if filepaths:
                slug_sources.append(Path(filepaths[0]).stem)
            for source in slug_sources:
                cleaned = (source or "").replace("-", " ").strip()
                if not cleaned:
                    continue
                dbrand, dbconf, dsize, dsconf = self._detect_brand_size(cleaned)
                if (not brand or not brand.strip()) and dbrand:
                    brand, brand_conf = dbrand, f"MetaSlug/{dbconf}"
                if (not size or not size.strip()) and dsize:
                    size, size_conf = dsize, f"MetaSlug/{dsconf}"
                if brand and size:
                    break
        return (brand or None, brand_conf, size or None, size_conf)
def preprocess_for_ocr(img_path: Path) -> Path:
    """
    Prepare a photo for OCR by boosting contrast and removing noise.

    This mirrors the legacy helper from `main.py` so tests and other modules
    can reuse the same preprocessing logic without importing the web app.
    """
    try:
        from PIL import Image, ImageEnhance, ImageFilter, ImageOps

        im = Image.open(img_path)
        im = im.convert("L")
        im = ImageOps.autocontrast(im)
        im = ImageEnhance.Contrast(im).enhance(1.6)
        im = im.filter(ImageFilter.MedianFilter(size=3))
        im = im.point(lambda p: 255 if p > 160 else 0)
        out = img_path.with_suffix(".ocr.jpg")
        im.save(out, quality=85)
        return out
    except Exception as exc:  # pragma: no cover - best effort
        logger.warning("ocr_preprocess_failed", path=str(img_path), error=str(exc))
        return img_path
def _normalize_metadata(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Return a sanitized copy of the provided metadata payload."""
    if not isinstance(payload, dict):
        return {}
    cleaned: Dict[str, Any] = {}
    for key, value in payload.items():
        if isinstance(key, str):
            key_lower = key.lower()
            if key_lower in _NORMALIZED_TEXT_KEYS or key_lower in _NESTED_METADATA_KEYS:
                target_key: Any = key_lower
            else:
                target_key = key
        else:
            target_key = key
        if isinstance(value, str):
            cleaned_value: Any = value.strip()
        elif isinstance(value, dict):
            cleaned_value = _normalize_metadata(value)
        else:
            cleaned_value = value
        cleaned[target_key] = cleaned_value
    return cleaned
def _detect_colour_from_photos(
    detector: ColourDetector,
    photos: Sequence[ProcessedPhoto],
) -> str:
    """Return the dominant colour for the first available photo."""
    if not photos:
        return "Unknown"
    try:
        return detector(photos[0].optimised)
    except Exception as exc:  # pragma: no cover - detector errors are rare
        logger.warning("colour_detect_failed", error=str(exc))
        return "Unknown"
