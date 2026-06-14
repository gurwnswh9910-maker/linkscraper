# -*- coding: utf-8 -*-
"""Restore bundled compressed CSV inputs."""

from __future__ import annotations

import base64
import gzip
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
INPUT_DIR = ROOT / "input"
BUNDLED = INPUT_DIR / "three_account_threads_urls_20260614.csv.gz.b64"
OUTPUT = INPUT_DIR / "three_account_threads_urls_20260614.csv"


def main() -> int:
    if not BUNDLED.exists():
        raise SystemExit(f"missing bundled input: {BUNDLED}")
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = base64.b64decode(BUNDLED.read_text(encoding="ascii"))
    OUTPUT.write_bytes(gzip.decompress(payload))
    print(f"restored={OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
