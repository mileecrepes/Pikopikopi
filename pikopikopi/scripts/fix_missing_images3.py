#!/usr/bin/env python3
"""
Direct fetch: use known Wikimedia Commons filenames for specific coffee classes.
These are well-known files that definitely contain the right coffee photos.
"""
from __future__ import annotations
import csv
import os
import re
import time
from pathlib import Path
from urllib.parse import quote

import requests

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.getenv("DATA_DIR", str(ROOT / "data"))).resolve()
IMAGE_ROOT = DATA_DIR / "images"
OUTCSV = DATA_DIR / "coffee_image_metadata.csv"
API = "https://commons.wikimedia.org/w/api.php"
HEADERS = {"User-Agent": "PikopikopiDatasetBuilder/1.0 (educational coffee discovery site)"}

# Known good Wikimedia Commons files for each missing class
DIRECT_FILES = {
    "ristretto": [
        "File:Ristretto.jpg",
        "File:Ristretto Chiang Mai.jpg",
        "File:Ristretto shot.jpg",
        "File:Espresso ristretto.jpg",
        "File:Caffe macchiato vs ristretto 2.jpg",
    ],
    "cold_brew": [
        "File:Cold brew coffee.jpg",
        "File:Cold-brew coffee.jpg",
        "File:Cold Brew Coffee.jpg",
        "File:Cold brew coffee in a glass.jpg",
        "File:Cold brew coffee jar.jpg",
    ],
    "latte_macchiato": [
        "File:Latte macchiato.jpg",
        "File:Latte macchiato coffee.jpg",
        "File:Latte Macchiato.jpg",
        "File:Latte-macchiato.jpg",
        "File:Starbucks Latte Macchiato.jpg",
    ],
}

def safe_filename(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value)
    return value[:140] or "coffee_image"

def metadata(info: dict, key: str) -> str:
    return str((info.get("extmetadata") or {}).get(key, {}).get("value") or "").strip()

def fetch_imageinfo(title: str) -> dict | None:
    """Fetch imageinfo for a specific Wikimedia Commons file."""
    params = {
        "action": "query", "format": "json", "titles": title,
        "prop": "imageinfo", "iiprop": "url|extmetadata", "iiurlwidth": 720,
    }
    response = requests.get(API, params=params, headers=HEADERS, timeout=35)
    response.raise_for_status()
    pages = response.json().get("query", {}).get("pages", {})
    for page in pages.values():
        if page.get("missing") is not None:
            return None
        imageinfo_list = page.get("imageinfo") or []
        if imageinfo_list:
            return imageinfo_list[0]
    return None

def main():
    PER_CLASS = 3
    PAUSE = 1.0

    old_rows: list[dict] = []
    if OUTCSV.exists():
        with OUTCSV.open(encoding="utf-8", newline="") as f:
            old_rows = list(csv.DictReader(f))
    by_filename = {row.get("filename"): row for row in old_rows if row.get("filename")}

    session = requests.Session()
    session.headers.update(HEADERS)

    for label, file_titles in DIRECT_FILES.items():
        folder = IMAGE_ROOT / label
        folder.mkdir(parents=True, exist_ok=True)

        existing = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}]
        count = len(existing)
        if count >= PER_CLASS:
            print(f"[skip] {label}: {count} images already present")
            continue

        print(f"[fetch] {label} (need {PER_CLASS - count} more)")
        for title in file_titles:
            if count >= PER_CLASS:
                break
            try:
                imageinfo = fetch_imageinfo(title)
                time.sleep(PAUSE)
            except Exception as exc:
                print(f"  [warning] Fetch failed for {title}: {exc}")
                time.sleep(PAUSE * 2)
                continue

            if not imageinfo:
                print(f"  [missing] {title}")
                continue

            url = imageinfo.get("thumburl") or imageinfo.get("url")
            if not url:
                continue
            suffix = Path(str(url).split("?")[0]).suffix.lower()
            if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
                suffix = ".jpg"
            filename = safe_filename(title.removeprefix("File:"))
            if not filename.lower().endswith(suffix):
                filename += suffix
            destination = folder / filename
            if destination.exists():
                count += 1
                print(f"  [exists] {filename}")
                continue
            try:
                image_response = session.get(url, timeout=40)
                image_response.raise_for_status()
                if len(image_response.content) < 10_000:
                    print(f"  [tiny] {title}")
                    continue
                destination.write_bytes(image_response.content)
            except Exception as exc:
                print(f"  [warning] Download failed for {title}: {exc}")
                continue

            source_page = "https://commons.wikimedia.org/wiki/" + quote(title.replace(" ", "_"))
            relative = str(destination.relative_to(DATA_DIR)).replace("\\", "/")
            by_filename[relative] = {
                "filename": relative, "label": label,
                "display_name": label.replace("_", " ").title(),
                "source_page": source_page, "image_url": imageinfo.get("url", ""),
                "license": metadata(imageinfo, "LicenseShortName"),
                "license_url": metadata(imageinfo, "LicenseUrl"),
                "artist_credit": metadata(imageinfo, "Artist"),
                "credit": metadata(imageinfo, "Credit"),
            }
            count += 1
            print(f"  {count}/{PER_CLASS}: {title}")

        if count < PER_CLASS:
            print(f"[note] {label}: only {count} valid images. Will use placeholder for missing.")

    fields = ["filename", "label", "display_name", "source_page", "image_url", "license", "license_url", "artist_credit", "credit"]
    with OUTCSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(by_filename.values())
    print(f"\nDone. Metadata rows: {len(by_filename)}")

if __name__ == "__main__":
    main()
