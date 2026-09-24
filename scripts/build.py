#!/usr/bin/env python3
"""Package the add-on into a distributable .ankiaddon file."""

from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "speedup"
DIST = ROOT / "dist"
OUTPUT = DIST / "speedup.ankiaddon"

SKIP_SUFFIXES = (".pyc",)
SKIP_DIRS = {"__pycache__"}


def validate() -> None:
    with (SRC / "manifest.json").open(encoding="utf-8") as handle:
        json.load(handle)
    with (SRC / "config.json").open(encoding="utf-8") as handle:
        json.load(handle)


def build() -> Path:
    validate()
    DIST.mkdir(exist_ok=True)
    if OUTPUT.exists():
        OUTPUT.unlink()

    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(SRC.rglob("*")):
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            if path.suffix in SKIP_SUFFIXES:
                continue
            if path.is_file():
                archive.write(path, path.relative_to(SRC))
    return OUTPUT


def main() -> None:
    output = build()
    print(f"Built {output} ({output.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
