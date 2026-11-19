#!/usr/bin/env python3
"""
Download a labeled coffee image dataset from Wikimedia Commons.
Target: 20 classes x 5 images = 100 images.
Images are stored by class folder and metadata.csv includes source/license attribution.
Requires: pip install requests
"""
from pathlib import Path
import csv, re, time, requests

ROOT = Path(__file__).resolve().parent
IMAGES = ROOT / "images"
OUTCSV = ROOT / "metadata.csv"
PER_CLASS = 5
WIDTH = 640
API = "https://commons.wikimedia.org/w/api.php"
HEADERS = {"User-Agent": "CoffeeImageDatasetBuilder/1.0 (educational dataset; contact: dataset-builder)"}

CLASSES = [
    ("espresso", "espresso coffee"), ("americano", "caffe americano coffee"),
    ("cappuccino", "cappuccino coffee"), ("caffe_latte", "caffe latte coffee"),
    ("mocha", "cafe mocha coffee"), ("flat_white", "flat white coffee"),
    ("macchiato", "coffee macchiato"), ("latte_macchiato", "latte macchiato coffee"),
    ("cortado", "cortado coffee"), ("affogato", "affogato coffee"),
    ("ristretto", "ristretto coffee"), ("lungo", "lungo coffee"),
    ("cafe_au_lait", "cafe au lait coffee"), ("cafe_bombon", "cafe bombon coffee"),
    ("cafe_con_leche", "cafe con leche coffee"),
    ("vietnamese_iced_coffee", "Vietnamese iced coffee ca phe sua da"),
    ("cold_brew", "cold brew coffee"), ("iced_coffee", "iced coffee"),
    ("blended_coffee", "frappuccino blended coffee drink"), ("irish_coffee", "Irish coffee")
]

def clean_filename(name):
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    return name[:150]

def search_files(query, limit=30):
    params = {
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": f"file:{query}", "gsrnamespace": 6, "gsrlimit": limit,
        "prop": "imageinfo", "iiprop": "url|extmetadata", "iiurlwidth": WIDTH
    }
    r = requests.get(API, params=params, headers=HEADERS, timeout=30)
    r.raise_for_status()
    pages = r.json().get("query", {}).get("pages", {})
    return list(pages.values())

def meta(info, key):
    return (info.get("extmetadata", {}).get(key, {}).get("value") or "").strip()

def main():
    records = []
    for label, query in CLASSES:
        folder = IMAGES / label
        folder.mkdir(parents=True, exist_ok=True)
        existing = list(folder.glob("*.jpg")) + list(folder.glob("*.png")) + list(folder.glob("*.webp"))
        if len(existing) >= PER_CLASS:
            print(f"[skip] {label}: already has {len(existing)} files")
            continue

        print(f"Searching: {label} ({query})")
        try:
            pages = search_files(query, 40)
        except Exception as e:
            print("Search failed:", e)
            continue

        count = len(existing)
        seen = set()
        for page in pages:
            if count >= PER_CLASS: break
            title = page.get("title", "")
            if title in seen: continue
            seen.add(title)
            imageinfo = (page.get("imageinfo") or [{}])[0]
            url = imageinfo.get("thumburl") or imageinfo.get("url")
            if not url: continue
            ext = Path(url.split("?")[0]).suffix.lower()
            if ext not in (".jpg", ".jpeg", ".png", ".webp"): ext = ".jpg"
            filename = clean_filename(title.replace("File:", "")) 
            if not filename.lower().endswith(ext): filename += ext
            dest = folder / filename
            try:
                resp = requests.get(url, headers=HEADERS, timeout=45)
                resp.raise_for_status()
                if len(resp.content) < 10_000: continue
                dest.write_bytes(resp.content)
            except Exception as e:
                print("Download failed:", title, e)
                continue

            lic = meta(imageinfo, "LicenseShortName")
            artist = meta(imageinfo, "Artist")
            credit = meta(imageinfo, "Credit")
            license_url = meta(imageinfo, "LicenseUrl")
            source_page = "https://commons.wikimedia.org/wiki/" + title.replace(" ", "_")
            records.append({
                "filename": str(dest.relative_to(ROOT)), "label": label,
                "display_name": dict(CLASSES).get(label, label),
                "source_page": source_page, "image_url": imageinfo.get("url", ""),
                "license": lic, "license_url": license_url,
                "artist_credit": artist, "credit": credit
            })
            count += 1
            print(f"  {count}/{PER_CLASS}: {title}")
            time.sleep(0.4)

        if count < PER_CLASS:
            print(f"WARNING: {label} only has {count} images; rerun or manually add more.")

    # Merge metadata with existing entries to support incremental runs.
    old = []
    if OUTCSV.exists():
        with OUTCSV.open(encoding="utf-8", newline="") as f:
            old = list(csv.DictReader(f))
    by_filename = {r.get("filename"): r for r in old}
    for r in records: by_filename[r["filename"]] = r
    fields = ["filename","label","display_name","source_page","image_url","license","license_url","artist_credit","credit"]
    with OUTCSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(by_filename.values())
    print(f"Done. Metadata rows: {len(by_filename)}")
    print("Check each image's license and attribution requirements before reuse.")

if __name__ == "__main__":
    main()
