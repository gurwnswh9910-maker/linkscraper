# -*- coding: utf-8 -*-
"""Restore bundled compressed CSV inputs."""

from __future__ import annotations

import base64
import gzip
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
INPUT_DIR = ROOT / "input"
SINGLE_BUNDLED = INPUT_DIR / "three_account_threads_urls_20260614.csv.gz.b64"
PART_PATTERN = "three_account_threads_urls_20260614.csv.gz.b64.part*"
OUTPUT = INPUT_DIR / "three_account_threads_urls_20260614.csv"


def read_bundled_base64() -> str:
    parts = sorted(INPUT_DIR.glob(PART_PATTERN))
    if parts:
        return "".join(part.read_text(encoding="ascii").strip() for part in parts)
    if SINGLE_BUNDLED.exists():
        return SINGLE_BUNDLED.read_text(encoding="ascii").strip()
    raise SystemExit(f"missing bundled input parts in: {INPUT_DIR}")


def main() -> int:
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = base64.b64decode(read_bundled_base64())
    OUTPUT.write_bytes(gzip.decompress(payload))
    print(f"restored={OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
