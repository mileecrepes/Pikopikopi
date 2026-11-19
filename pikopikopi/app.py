from __future__ import annotations

import csv
import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import sqlite3
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent
SEED_DIR = ROOT / "seed_data"
DATA_DIR = Path(os.getenv("DATA_DIR", str(ROOT / "data"))).resolve()
IMAGE_DIR = DATA_DIR / "images"
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "pikopikopi.sqlite3"
DATASET_PATH = DATA_DIR / "coffee_survey.csv"
CLASS_PATH = DATA_DIR / "class_labels.csv"
METADATA_PATH = DATA_DIR / "coffee_image_metadata.csv"
CATALOG_PATH = ROOT / "catalog.json"
SECRET_KEY = os.getenv("SECRET_KEY") or secrets.token_hex(32)
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
COOKIE_NAME = "pikopikopi_admin"

app = FastAPI(title="Pikopikopi", version="1.0.0")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


def bootstrap_files() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    for source, target in [
        (SEED_DIR / "coffee_survey.csv", DATASET_PATH),
        (SEED_DIR / "class_labels.csv", CLASS_PATH),
        (SEED_DIR / "metadata_template.csv", DATA_DIR / "metadata_template.csv"),
    ]:
        if source.exists() and not target.exists():
            shutil.copy2(source, target)


def db() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS banners (
                id TEXT PRIMARY KEY,
                sponsor TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                keywords TEXT NOT NULL,
                target_url TEXT DEFAULT '',
                image_file TEXT DEFAULT '',
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()


def load_catalog() -> list[dict[str, Any]]:
    # catalog.json is the canonical display/profile source; class_labels.csv is
    # retained as the source list for image-class bookkeeping.
    with CATALOG_PATH.open(encoding="utf-8") as f:
        return json.load(f)


CATALOG = load_catalog()


def normalize(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def find_alias_mapping() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for item in CATALOG:
        mapping[normalize(item["display_name"])] = item["label"]
        for alias in item.get("aliases", []):
            mapping[normalize(alias)] = item["label"]
    mapping.update({
        "blended drink e g frappuccino": "blended_coffee",
        "caffe latte": "caffe_latte",
        "cafe latte": "caffe_latte",
        "flat white": "flat_white",
    })
    return mapping


ALIAS_MAP = find_alias_mapping()


def load_survey_stats() -> dict[str, Any]:
    stats: dict[str, Any] = {
        "respondents": 0,
        "taste_responses": 0,
        "drink_votes": {item["label"]: 0 for item in CATALOG},
        "taste_counts": {},
        "taste_total": 0,
        "samples": {},
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if not DATASET_PATH.exists():
        return stats

    taste_field = "Before today's tasting, which of the following best described what kind of coffee you like?"
    drink_field = "What is your favorite coffee drink?"
    specified_field = "Please specify what your favorite coffee drink is"
    with DATASET_PATH.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            stats["respondents"] += 1
            drink = normalize(row.get(drink_field))
            if drink in ALIAS_MAP:
                stats["drink_votes"][ALIAS_MAP[drink]] += 1
            elif drink == "blended drink e g frappuccino":
                stats["drink_votes"]["blended_coffee"] += 1
            elif drink == "other":
                specified = normalize(row.get(specified_field))
                for alias, label in ALIAS_MAP.items():
                    if specified and (specified == alias or alias in specified or specified in alias):
                        stats["drink_votes"][label] += 1
                        break

            taste = str(row.get(taste_field, "") or "").strip()
            if taste:
                stats["taste_responses"] += 1
                key = normalize(taste).replace(" ", "_")
                stats["taste_counts"][key] = stats["taste_counts"].get(key, 0) + 1

    stats["taste_total"] = sum(stats["taste_counts"].values())
    for sample in "ABCD":
        sample_info: dict[str, Any] = {}
        for metric in ["Bitterness", "Acidity", "Personal Preference"]:
            field = f"Coffee {sample} - {metric}"
            vals: list[float] = []
            with DATASET_PATH.open(encoding="utf-8-sig", newline="") as f:
                for row in csv.DictReader(f):
                    try:
                        vals.append(float(row.get(field, "")))
                    except (TypeError, ValueError):
                        pass
            sample_info[metric.lower().replace(" ", "_")] = round(sum(vals) / len(vals), 2) if vals else None
            sample_info[metric.lower().replace(" ", "_") + "_n"] = len(vals)
        stats["samples"][sample] = sample_info
    return stats


bootstrap_files()
init_db()
SURVEY_STATS = load_survey_stats()


def image_for(label: str) -> str:
    folder = IMAGE_DIR / label
    if folder.is_dir():
        files = sorted([p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}])
        if files:
            return f"/coffee-images/{label}/{files[0].name}"
    return "/static/images/coffee-placeholder.svg"


def get_metadata_credit(label: str, filename: str) -> str:
    if not METADATA_PATH.exists():
        return ""
    try:
        with METADATA_PATH.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                expected = Path(row.get("filename", "")).name
                if row.get("label") == label and expected == filename:
                    return " · ".join(x for x in [row.get("artist_credit", "").strip(), row.get("license", "").strip()] if x)
    except Exception:
        return ""
    return ""


def public_catalog() -> list[dict[str, Any]]:
    result = []
    for item in CATALOG:
        clone = dict(item)
        clone["survey_votes"] = int(SURVEY_STATS["drink_votes"].get(item["label"], 0))
        clone["image"] = image_for(item["label"])
        folder = IMAGE_DIR / item["label"]
        files = sorted([p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}]) if folder.is_dir() else []
        clone["image_count"] = len(files)
        clone["image_credit"] = get_metadata_credit(item["label"], files[0].name) if files else ""
        result.append(clone)
    return result


def safe_preference(value: Any, allowed: set[str] | None = None) -> str:
    s = normalize(value).replace(" ", "_")
    return s if not allowed or s in allowed else ""


def recommend(payload: dict[str, Any]) -> list[dict[str, Any]]:
    taste_allowed = {tag for item in CATALOG for tag in item.get("tags", [])}
    taste = safe_preference(payload.get("taste"), taste_allowed)
    search_query = normalize(payload.get("search"))
    roast = safe_preference(payload.get("roast"), {"light", "medium", "dark"})
    drink_type = safe_preference(payload.get("drink_type"), {item["label"] for item in CATALOG})
    try:
        bitterness = int(payload.get("bitterness")) if payload.get("bitterness") not in (None, "", "any") else None
    except (ValueError, TypeError):
        bitterness = None
    try:
        acidity = int(payload.get("acidity")) if payload.get("acidity") not in (None, "", "any") else None
    except (ValueError, TypeError):
        acidity = None
    try:
        strength = int(payload.get("strength")) if payload.get("strength") not in (None, "", "any") else None
    except (ValueError, TypeError):
        strength = None
    for name, value in [("bitterness", bitterness), ("acidity", acidity), ("strength", strength)]:
        if value is not None and not 1 <= value <= 5:
            raise HTTPException(status_code=400, detail=f"Nilai {name} harus antara 1 sampai 5.")

    filtered = [item for item in CATALOG if not drink_type or item["label"] == drink_type]
    scored: list[dict[str, Any]] = []
    weights: dict[str, int] = {}
    if taste: weights["taste"] = 30
    if search_query: weights["search"] = 10
    if bitterness is not None: weights["bitterness"] = 20
    if acidity is not None: weights["acidity"] = 20
    if strength is not None: weights["strength"] = 15
    if roast: weights["roast"] = 15

    max_votes = max(SURVEY_STATS["drink_votes"].values()) if SURVEY_STATS["drink_votes"] else 1
    if max_votes == 0: max_votes = 1
    for item in filtered:
        components: dict[str, float] = {}
        if taste:
            components["taste"] = 1.0 if taste in item.get("tags", []) else 0.0
        if search_query:
            searchable = normalize(" ".join([item.get("display_name", ""), item.get("description", ""), item.get("label", ""), " ".join(item.get("tags", [])), " ".join(item.get("aliases", []))]))
            query_tokens = [token for token in search_query.split() if len(token) > 1]
            components["search"] = 1.0 if (search_query in searchable or (query_tokens and any(token in searchable for token in query_tokens))) else 0.0
        if bitterness is not None:
            components["bitterness"] = 1 - abs(bitterness - int(item["bitterness"])) / 4
        if acidity is not None:
            components["acidity"] = 1 - abs(acidity - int(item["acidity"])) / 4
        if strength is not None:
            components["strength"] = 1 - abs(strength - int(item["strength"])) / 4
        if roast:
            components["roast"] = 1.0 if roast == item["roast"] else (0.45 if abs({"light":1,"medium":2,"dark":3}[roast] - {"light":1,"medium":2,"dark":3}[item["roast"]]) == 1 else 0.0)

        votes = int(SURVEY_STATS["drink_votes"].get(item["label"], 0))
        if weights:
            base = sum(components[k] * w for k, w in weights.items()) / sum(weights.values())
            # A small popularity adjustment breaks close matches without dominating selected preferences.
            score = min(100, max(0, round(base * 94 + 6 * (votes / max_votes), 1)))
        else:
            score = round(75 + 25 * votes / max_votes, 1) if votes else 65.0

        reasons: list[str] = []
        if taste and taste in item.get("tags", []): reasons.append(f"Memiliki karakter {taste.replace('_', ' ')}")
        if bitterness is not None and abs(bitterness - item["bitterness"]) <= 1: reasons.append("Tingkat pahit mendekati preferensimu")
        if acidity is not None and abs(acidity - item["acidity"]) <= 1: reasons.append("Tingkat acidity mendekati preferensimu")
        if strength is not None and abs(strength - item["strength"]) <= 1: reasons.append("Kekuatan rasa sesuai pilihanmu")
        if roast and roast == item["roast"]: reasons.append(f"Roast {roast}")
        if not reasons and votes: reasons.append("Cukup banyak dipilih responden survei")
        if not reasons: reasons.append("Alternatif untuk dieksplorasi")

        clone = dict(item)
        available_files = sorted([p for p in (IMAGE_DIR / item["label"]).iterdir() if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}]) if (IMAGE_DIR / item["label"]).is_dir() else []
        clone.update({
            "match_score": score,
            "survey_votes": votes,
            "image": image_for(item["label"]),
            "image_count": len(available_files),
            "image_credit": get_metadata_credit(item["label"], available_files[0].name) if available_files else "",
            "match_reasons": reasons[:3],
            "profile_basis": "Estimasi karakter umum minuman; bukan pengukuran langsung dari dataset.",
        })
        scored.append(clone)
    scored.sort(key=lambda x: (x["match_score"], x["survey_votes"]), reverse=True)
    try:
        limit = int(payload.get("limit", 5))
    except (ValueError, TypeError):
        limit = 5
    limit = 10 if limit >= 10 else 5
    return scored[:limit]


def is_admin(request: Request) -> bool:
    expected = hmac.new(SECRET_KEY.encode(), b"pikopikopi-admin", hashlib.sha256).hexdigest()
    provided = request.cookies.get(COOKIE_NAME, "")
    return bool(provided) and hmac.compare_digest(provided, expected)


def require_admin(request: Request) -> None:
    if not is_admin(request):
        raise HTTPException(status_code=401, detail="Silakan login sebagai admin terlebih dahulu.")


def validate_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=400, detail="Link sponsor harus menggunakan URL http:// atau https://.")
    return url


@app.get("/")
async def home():
    return FileResponse(ROOT / "templates" / "index.html")


@app.get("/admin")
async def admin_page():
    return FileResponse(ROOT / "templates" / "admin.html")


@app.get("/api/health")
async def health():
    return {"status": "ok", "app": "Pikopikopi"}


@app.get("/api/stats")
async def stats():
    sample_d = SURVEY_STATS["samples"].get("D", {})
    image_count = sum(len(list(folder.glob("*"))) for folder in IMAGE_DIR.iterdir() if folder.is_dir()) if IMAGE_DIR.exists() else 0
    return {
        "respondents": SURVEY_STATS["respondents"],
        "taste_responses": SURVEY_STATS["taste_responses"],
        "catalog_count": len(CATALOG),
        "image_count": image_count,
        "top_tastes": sorted(SURVEY_STATS["taste_counts"].items(), key=lambda x: x[1], reverse=True)[:6],
        "sample_d_average_preference": sample_d.get("personal_preference"),
    }


@app.get("/api/catalog")
async def catalog():
    return {"items": public_catalog()}


@app.post("/api/recommendations")
async def recommendations(request: Request):
    payload = await request.json()
    results = recommend(payload if isinstance(payload, dict) else {})
    return {"results": results, "count": len(results), "basis": "Survei preferensi + estimasi karakter umum minuman."}


@app.get("/api/banner")
async def get_banner(q: str = ""):
    search_text = normalize(q)
    if not search_text:
        return {"banner": None}
    with db() as conn:
        rows = conn.execute("SELECT * FROM banners WHERE active = 1 ORDER BY created_at DESC").fetchall()
    for row in rows:
        try:
            keywords = json.loads(row["keywords"])
        except Exception:
            keywords = []
        for keyword in keywords:
            k = normalize(keyword)
            if k and (k in search_text or search_text in k):
                return {"banner": {
                    "id": row["id"], "sponsor": row["sponsor"], "title": row["title"],
                    "description": row["description"], "target_url": row["target_url"],
                    "image_url": f"/uploads/{row['image_file']}" if row["image_file"] else ""
                }}
    return {"banner": None}


@app.get("/coffee-images/{label}/{filename}")
async def coffee_image(label: str, filename: str):
    if label not in {item["label"] for item in CATALOG} or Path(filename).name != filename:
        raise HTTPException(status_code=404, detail="Gambar tidak ditemukan.")
    path = (IMAGE_DIR / label / filename).resolve()
    if not path.is_file() or IMAGE_DIR not in path.parents:
        raise HTTPException(status_code=404, detail="Gambar tidak ditemukan.")
    return FileResponse(path)


@app.get("/uploads/{filename}")
async def uploaded_image(filename: str):
    if Path(filename).name != filename:
        raise HTTPException(status_code=404, detail="File tidak ditemukan.")
    path = (UPLOAD_DIR / filename).resolve()
    if not path.is_file() or UPLOAD_DIR not in path.parents:
        raise HTTPException(status_code=404, detail="File tidak ditemukan.")
    return FileResponse(path)


@app.post("/api/admin/login")
async def admin_login(request: Request):
    if not ADMIN_PASSWORD:
        raise HTTPException(status_code=503, detail="ADMIN_PASSWORD belum diatur di environment website.")
    payload = await request.json()
    password = str(payload.get("password", ""))
    if not hmac.compare_digest(password, ADMIN_PASSWORD):
        raise HTTPException(status_code=401, detail="Password admin tidak sesuai.")
    token = hmac.new(SECRET_KEY.encode(), b"pikopikopi-admin", hashlib.sha256).hexdigest()
    response = JSONResponse({"ok": True})
    response.set_cookie(COOKIE_NAME, token, httponly=True, secure=os.getenv("COOKIE_SECURE", "0") == "1", samesite="strict", max_age=60*60*12, path="/")
    return response


@app.post("/api/admin/logout")
async def admin_logout():
    response = JSONResponse({"ok": True})
    response.delete_cookie(COOKIE_NAME, path="/")
    return response


@app.get("/api/admin/status")
async def admin_status(request: Request):
    return {"authenticated": is_admin(request), "password_configured": bool(ADMIN_PASSWORD)}


@app.get("/api/admin/banners")
async def admin_banners(request: Request):
    require_admin(request)
    with db() as conn:
        rows = conn.execute("SELECT * FROM banners ORDER BY created_at DESC").fetchall()
    result = []
    for row in rows:
        result.append({
            "id": row["id"], "sponsor": row["sponsor"], "title": row["title"],
            "description": row["description"], "keywords": json.loads(row["keywords"]),
            "target_url": row["target_url"], "image_url": f"/uploads/{row['image_file']}" if row["image_file"] else "",
            "active": bool(row["active"]), "created_at": row["created_at"]
        })
    return {"banners": result}


@app.post("/api/admin/upload-banner-image")
async def upload_banner_image(request: Request, file: UploadFile = File(...)):
    require_admin(request)
    ext = Path(file.filename or "").suffix.lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
        raise HTTPException(status_code=400, detail="Gunakan gambar JPG, PNG, atau WEBP.")
    content = await file.read()
    if len(content) > 8 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Ukuran gambar maksimal 8 MB.")
    filename = f"banner_{uuid.uuid4().hex}{ext}"
    (UPLOAD_DIR / filename).write_bytes(content)
    return {"filename": filename, "image_url": f"/uploads/{filename}"}


@app.post("/api/admin/banners")
async def create_banner(request: Request):
    require_admin(request)
    payload = await request.json()
    sponsor = str(payload.get("sponsor", "")).strip()
    title = str(payload.get("title", "")).strip()
    if not sponsor or not title:
        raise HTTPException(status_code=400, detail="Nama sponsor dan judul banner wajib diisi.")
    raw_keywords = payload.get("keywords", [])
    if isinstance(raw_keywords, str):
        raw_keywords = raw_keywords.split(",")
    keywords = [str(x).strip() for x in raw_keywords if str(x).strip()]
    if not keywords:
        raise HTTPException(status_code=400, detail="Masukkan minimal satu kata kunci pemicu banner.")
    image_file = str(payload.get("image_file", "")).strip()
    if image_file and Path(image_file).name != image_file:
        raise HTTPException(status_code=400, detail="Nama file gambar tidak valid.")
    target_url = validate_url(str(payload.get("target_url", "")))
    banner_id = uuid.uuid4().hex[:12]
    created = datetime.now(timezone.utc).isoformat()
    with db() as conn:
        conn.execute(
            "INSERT INTO banners (id,sponsor,title,description,keywords,target_url,image_file,active,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (banner_id, sponsor, title, str(payload.get("description", "")).strip(), json.dumps(keywords, ensure_ascii=False), target_url, image_file, 1 if payload.get("active", True) else 0, created)
        )
        conn.commit()
    return {"ok": True, "id": banner_id}


@app.patch("/api/admin/banners/{banner_id}")
async def update_banner(banner_id: str, request: Request):
    require_admin(request)
    payload = await request.json()
    active = 1 if payload.get("active") else 0
    with db() as conn:
        cur = conn.execute("UPDATE banners SET active = ? WHERE id = ?", (active, banner_id))
        conn.commit()
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Banner tidak ditemukan.")
    return {"ok": True}


@app.delete("/api/admin/banners/{banner_id}")
async def delete_banner(banner_id: str, request: Request):
    require_admin(request)
    with db() as conn:
        cur = conn.execute("DELETE FROM banners WHERE id = ?", (banner_id,))
        conn.commit()
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Banner tidak ditemukan.")
    return {"ok": True}


@app.post("/api/admin/upload-coffee-images")
async def upload_coffee_images(
    request: Request,
    label: str = Form(...),
    files: list[UploadFile] = File(...),
    credit: str = Form(""),
    license: str = Form(""),
    source_url: str = Form(""),
):
    require_admin(request)
    if label not in {item["label"] for item in CATALOG}:
        raise HTTPException(status_code=400, detail="Jenis minuman tidak dikenal.")
    if not files or len(files) > 20:
        raise HTTPException(status_code=400, detail="Pilih antara 1 sampai 20 foto.")
    folder = IMAGE_DIR / label
    folder.mkdir(parents=True, exist_ok=True)
    saved = []
    metadata_rows = []
    for upload in files:
        ext = Path(upload.filename or "").suffix.lower()
        if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
            raise HTTPException(status_code=400, detail="Semua foto harus berformat JPG, PNG, atau WEBP.")
        content = await upload.read()
        if len(content) > 8 * 1024 * 1024:
            raise HTTPException(status_code=400, detail=f"Foto {upload.filename} melebihi batas 8 MB.")
        filename = f"{uuid.uuid4().hex}{ext}"
        (folder / filename).write_bytes(content)
        saved.append(filename)
        metadata_rows.append({
            "filename": f"images/{label}/{filename}", "label": label,
            "display_name": next((x["display_name"] for x in CATALOG if x["label"] == label), label),
            "source_page": source_url.strip(), "image_url": "", "license": license.strip(),
            "license_url": "", "artist_credit": credit.strip(), "credit": "Manual admin upload"
        })
    if any([credit.strip(), license.strip(), source_url.strip()]):
        file_exists = METADATA_PATH.exists()
        fields = ["filename", "label", "display_name", "source_page", "image_url", "license", "license_url", "artist_credit", "credit"]
        with METADATA_PATH.open("a", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            if not file_exists:
                writer.writeheader()
            writer.writerows(metadata_rows)
    return {"ok": True, "saved": len(saved), "label": label}


@app.get("/api/admin/dataset-status")
async def dataset_status(request: Request):
    require_admin(request)
    return {
        "filename": DATASET_PATH.name,
        "exists": DATASET_PATH.exists(),
        "size_bytes": DATASET_PATH.stat().st_size if DATASET_PATH.exists() else 0,
        "respondents": SURVEY_STATS["respondents"],
        "image_count": sum(len(list(folder.glob("*"))) for folder in IMAGE_DIR.iterdir() if folder.is_dir()),
    }


@app.post("/api/admin/dataset")
async def upload_dataset(request: Request, file: UploadFile = File(...)):
    global SURVEY_STATS
    require_admin(request)
    if Path(file.filename or "").suffix.lower() != ".csv":
        raise HTTPException(status_code=400, detail="Dataset harus berupa file CSV.")
    content = await file.read()
    if len(content) > 60 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Ukuran dataset maksimal 60 MB.")
    temp_path = DATA_DIR / f"upload_{uuid.uuid4().hex}.csv"
    temp_path.write_bytes(content)
    try:
        with temp_path.open(encoding="utf-8-sig", newline="") as f:
            headers = set(next(csv.reader(f), []))
        required = {
            "What is your favorite coffee drink?",
            "Before today's tasting, which of the following best described what kind of coffee you like?",
            "Coffee A - Bitterness", "Coffee A - Acidity", "Coffee A - Personal Preference"
        }
        if not required.issubset(headers):
            raise HTTPException(status_code=400, detail="Kolom wajib tidak ditemukan. Pastikan file menggunakan format survei Pikopikopi.")
        shutil.move(str(temp_path), str(DATASET_PATH))
        SURVEY_STATS = load_survey_stats()
    finally:
        if temp_path.exists(): temp_path.unlink()
    return {"ok": True, "respondents": SURVEY_STATS["respondents"]}


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
