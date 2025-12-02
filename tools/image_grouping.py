"""
Lightweight content-aware grouping for bulk uploads.

- Uses perceptual hashing (pHash) to cluster visually similar photos.
- Designed to stay Pi-friendly; no heavy deep-learning dependencies.
- Thresholds are tunable via function params (hash_threshold, fallback_time_gap_seconds,
  max_photos_per_group) and should be tweaked with real data.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from PIL import Image
import imagehash


@dataclass
class PhotoSample:
    id: Any
    path: str
    taken_at: Optional[float] = None


def compute_phash(path: str) -> imagehash.ImageHash:
    """
    Compute a perceptual hash for the given image path.
    Uses a robust pHash and normalises to RGB.
    """
    img = Image.open(path).convert("RGB")
    return imagehash.phash(img)


def group_photos_by_content(
    photos: List[PhotoSample],
    max_photos_per_group: int = 8,
    hash_threshold: int = 10,
    fallback_time_gap_seconds: float = 5 * 60,
) -> List[List[PhotoSample]]:
    """
    Group photos into visually-similar clusters.

    - photos: list of PhotoSample.
    - max_photos_per_group: cap per draft.
    - hash_threshold: max Hamming distance between a photo and a group's
      representative hash to be considered the same item.
    - fallback_time_gap_seconds: if the gap between two photos is huge,
      start a new group even if the hash looks similar.

    Returns: list of lists; each inner list is one draft group.
    """

    if not photos:
        return []

    photos_sorted = sorted(
        photos,
        key=lambda p: p.taken_at or 0.0,
    )

    groups: List[List[PhotoSample]] = []
    group_hashes: List[Optional[imagehash.ImageHash]] = []

    for photo in photos_sorted:
        try:
            ph = compute_phash(photo.path)
        except Exception:
            groups.append([photo])
            group_hashes.append(None)
            continue

        placed = False

        for g_idx, rep_hash in enumerate(group_hashes):
            if rep_hash is None:
                continue
            distance = ph - rep_hash
            if distance <= hash_threshold and len(groups[g_idx]) < max_photos_per_group:
                if (
                    photo.taken_at is not None
                    and groups[g_idx][-1].taken_at is not None
                    and photo.taken_at - groups[g_idx][-1].taken_at > fallback_time_gap_seconds
                ):
                    continue

                groups[g_idx].append(photo)
                placed = True
                break

        if not placed:
            groups.append([photo])
            group_hashes.append(ph)

    return groups
