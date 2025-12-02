"""
Tiny helper to visualise how bulk grouping clusters photos by content.

Usage:
    python tools/dev_debug_image_grouping.py path/to/a.jpg path/to/b.jpg ...
    python tools/dev_debug_image_grouping.py ./folder/of/images
"""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path
from typing import Iterable, List

from tools.image_grouping import PhotoSample, group_photos_by_content


def _iter_image_paths(paths: List[str]) -> Iterable[Path]:
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            for child in sorted(p.iterdir()):
                if child.is_file():
                    yield child
        elif p.exists():
            yield p


def _fake_timestamps(count: int, gap_seconds: float = 2.0) -> List[float]:
    base = time.time()
    return [base + i * gap_seconds for i in range(count)]


def main() -> None:
    parser = argparse.ArgumentParser(description="Dev helper to inspect image grouping behaviour.")
    parser.add_argument("images", nargs="+", help="Image paths or directories.")
    parser.add_argument("--max", dest="max_per_group", type=int, default=8, help="Max per group.")
    parser.add_argument("--hash-threshold", type=int, default=10, help="Hamming distance threshold.")
    parser.add_argument(
        "--fallback-gap",
        type=float,
        default=5 * 60,
        help="Fallback time gap in seconds before forcing a split.",
    )
    args = parser.parse_args()

    paths = list(_iter_image_paths(args.images))
    if not paths:
        print("No images found.")
        return

    timestamps = _fake_timestamps(len(paths))
    samples = [
        PhotoSample(id=idx, path=str(path), taken_at=timestamps[idx]) for idx, path in enumerate(paths)
    ]

    groups = group_photos_by_content(
        samples,
        max_photos_per_group=args.max_per_group,
        hash_threshold=args.hash_threshold,
        fallback_time_gap_seconds=args.fallback_gap,
    )

    print(f"[dev_debug] photos={len(samples)} groups={len(groups)}")
    for idx, group in enumerate(groups):
        print(f"- group {idx} size={len(group)}")
        for photo in group:
            print(f"    {photo.id}: {os.path.basename(photo.path)} (t={photo.taken_at})")


if __name__ == "__main__":
    main()
