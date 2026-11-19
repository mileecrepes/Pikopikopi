#!/usr/bin/env python3
"""Download up to five coffee-drink photos per catalog class from Wikimedia Commons.

Images and attribution metadata are saved under DATA_DIR so the app can serve
photos without exposing the private survey CSV. Every file's individual license
must still be checked before commercial reuse.
"""
from __future__ import annotations

import argparse
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
CLASSES = [
    ("espresso", "espresso coffee drink"), ("americano", "caffe americano drink"),
    ("cappuccino", "cappuccino coffee drink"), ("caffe_latte", "caffe latte drink"),
    ("mocha", "cafe mocha coffee drink"), ("flat_white", "flat white coffee drink"),
    ("macchiato", "coffee macchiato drink"), ("latte_macchiato", "latte macchiato drink"),
    ("cortado", "cortado coffee drink"), ("affogato", "affogato coffee dessert"),
    ("ristretto", "ristretto coffee drink"), ("lungo", "lungo coffee drink"),
    ("cafe_au_lait", "cafe au lait coffee drink"), ("cafe_bombon", "cafe bombon coffee drink"),
    ("cafe_con_leche", "cafe con leche coffee drink"),
    ("vietnamese_iced_coffee", "Vietnamese iced coffee ca phe sua da"),
    ("cold_brew", "cold brew coffee drink"), ("iced_coffee", "iced coffee drink"),
    ("blended_coffee", "blended coffee frappe drink"), ("pour_over", "pour over filter coffee V60"),
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-class", type=int, default=5)
    parser.add_argument("--pause", type=float, default=0.4)
    args = parser.parse_args()
    IMAGE_ROOT.mkdir(parents=True, exist_ok=True)

    old_rows: list[dict] = []
    if OUTCSV.exists():
        with OUTCSV.open(encoding="utf-8", newline="") as f:
            old_rows = list(csv.DictReader(f))
    by_filename = {row.get("filename"): row for row in old_rows if row.get("filename")}

    session = requests.Session()
    session.headers.update(HEADERS)
    for label, query in CLASSES:
        folder = IMAGE_ROOT / label
        folder.mkdir(parents=True, exist_ok=True)
        existing = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}]
        if len(existing) >= args.per_class:
            print(f"[skip] {label}: {len(existing)} images already present")
            continue
        print(f"[search] {label}: {query}")
        try:
            pages = search_files(query)
        except Exception as exc:
            print(f"[warning] Search failed for {label}: {exc}")
            continue

        seen: set[str] = set()
        count = len(existing)
        for page in pages:
            if count >= args.per_class:
                break
            title = str(page.get("title", ""))
            if not title or title in seen:
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
                print(f"[warning] Download failed for {title}: {exc}")
                continue

            source_page = "https://commons.wikimedia.org/wiki/" + quote(title.replace(" ", "_"))
            relative = str(destination.relative_to(DATA_DIR)).replace("\\", "/")
            by_filename[relative] = {
                "filename": relative,
                "label": label,
                "display_name": dict(CLASSES).get(label, label),
                "source_page": source_page,
                "image_url": imageinfo.get("url", ""),
                "license": metadata(imageinfo, "LicenseShortName"),
                "license_url": metadata(imageinfo, "LicenseUrl"),
                "artist_credit": metadata(imageinfo, "Artist"),
                "credit": metadata(imageinfo, "Credit"),
            }
            count += 1
            print(f"  {count}/{args.per_class}: {title}")
            time.sleep(args.pause)
        if count < args.per_class:
            print(f"[note] {label}: only {count} images found; run again or add photos manually")

    fields = ["filename", "label", "display_name", "source_page", "image_url", "license", "license_url", "artist_credit", "credit"]
    with OUTCSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(by_filename.values())
    print(f"Done. Images metadata rows: {len(by_filename)}")
    print("Review each license and attribution requirement before commercial use.")


if __name__ == "__main__":
    main()
