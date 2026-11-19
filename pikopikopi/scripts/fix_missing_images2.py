#!/usr/bin/env python3
"""
Second targeted fix: use very specific Wikimedia titles or categories for
ristretto, cold_brew, and latte_macchiato.
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

TARGETS = [
    ("ristretto", ["ristretto espresso shot", "ristretto coffee cup small", "espresso ristretto"]),
    ("cold_brew", ["cold brew coffee concentrate", "cold brew iced coffee bottle", "cold brew coffee mason jar"]),
    ("latte_macchiato", ["latte macchiato coffee glass", "latte macchiato coffee drink", "latte macchiato espresso milk"]),
]

JUNK_KEYWORDS = [
    ".pdf", ".djvu", "wet_magic", "nesbit", "tankard", "drinking_songs",
    "5555_result", "jacksmanualonvin", "colonialcookbook", "treatise_on",
    "library_of_congress", "trombone_coffeemaker", "working_late",
    "boyhood", "adulterations", "recollections", "frapp_coffee",
    "thackeray", "our_street", "donut", "beignet",
]

def safe_filename(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value)
    return value[:140] or "coffee_image"

def metadata(info: dict, key: str) -> str:
    return str((info.get("extmetadata") or {}).get(key, {}).get("value") or "").strip()

def search_files(query: str) -> list[dict]:
    params = {
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": f"file:{query}", "gsrnamespace": 6, "gsrlimit": 50,
        "prop": "imageinfo", "iiprop": "url|extmetadata", "iiurlwidth": 720,
    }
    response = requests.get(API, params=params, headers=HEADERS, timeout=35)
    response.raise_for_status()
    pages = response.json().get("query", {}).get("pages", {})
    return list(pages.values())

def is_valid(title: str) -> bool:
    t = title.lower()
    return not any(kw in t for kw in JUNK_KEYWORDS)

def main():
    PER_CLASS = 3
    PAUSE = 1.5

    old_rows: list[dict] = []
    if OUTCSV.exists():
        with OUTCSV.open(encoding="utf-8", newline="") as f:
            old_rows = list(csv.DictReader(f))
    by_filename = {row.get("filename"): row for row in old_rows if row.get("filename")}

    session = requests.Session()
    session.headers.update(HEADERS)

    for label, queries in TARGETS:
        folder = IMAGE_ROOT / label
        folder.mkdir(parents=True, exist_ok=True)

        existing = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}]
        count = len(existing)
        if count >= PER_CLASS:
            print(f"[skip] {label}: {count} images already present")
            continue

        print(f"[search] {label} (need {PER_CLASS - count} more)")
        for query in queries:
            if count >= PER_CLASS:
                break
            print(f"  query: {query}")
            try:
                pages = search_files(query)
            except Exception as exc:
                print(f"  [warning] Search failed: {exc}")
                time.sleep(PAUSE * 2)
                continue

            seen: set[str] = set()
            for page in pages:
                if count >= PER_CLASS:
                    break
                title = str(page.get("title", ""))
                if not title or title in seen or not is_valid(title):
                    continue
                seen.add(title)
                imageinfo = (page.get("imageinfo") or [{}])[0]
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
                    continue
                try:
                    image_response = session.get(url, timeout=40)
                    image_response.raise_for_status()
                    if len(image_response.content) < 10_000:
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
                time.sleep(PAUSE)

        if count < PER_CLASS:
            print(f"[note] {label}: only {count} valid images found")

    fields = ["filename", "label", "display_name", "source_page", "image_url", "license", "license_url", "artist_credit", "credit"]
    with OUTCSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(by_filename.values())
    print(f"\nDone. Metadata rows: {len(by_filename)}")

if __name__ == "__main__":
    main()
