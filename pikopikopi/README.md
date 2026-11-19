# Pikopikopi

Website rekomendasi minuman kopi dengan tampilan responsif, katalog 20 jenis minuman, foto asli dari Wikimedia Commons, pencarian kata kunci, filter selera, rekomendasi Top 5/Top 10, panel admin banner sponsor berbasis kata kunci, serta pengelolaan dataset CSV.

## Isi project

- `app.py` — API FastAPI, perhitungan rekomendasi, autentikasi admin, penyimpanan banner dan dataset.
- `templates/` — halaman pengunjung dan dashboard admin.
- `static/` — CSS, JavaScript, dan ilustrasi fallback ketika foto aktual belum tersedia.
- `seed_data/coffee_survey.csv` — dataset survei yang kamu unggah (disimpan privat di server; tidak disajikan sebagai file publik).
- `seed_data/class_labels.csv` — daftar jenis minuman yang digunakan katalog publik.
- `catalog.json` — profil umum minuman untuk membantu pencocokan awal.
- `scripts/download_coffee_images.py` — pengunduh foto dan metadata lisensi dari Wikimedia Commons.
- `start.sh` — startup script untuk deployment: mengunduh foto otomatis pada first run, lalu menjalankan server.
- `render.yaml` dan `Dockerfile` — konfigurasi deployment dengan persistent disk.

## Jalankan secara lokal

Membutuhkan Python 3.10+.

### Windows (cara mudah)
```
run_local_windows.bat
```
Script ini akan:
1. Membuat virtual environment secara otomatis
2. Install semua dependencies
3. Download foto kopi dari Wikimedia Commons (hanya pertama kali)
4. Menjalankan server di `http://localhost:8000`

### Manual (Windows PowerShell / macOS / Linux)
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python scripts/download_coffee_images.py --per-class 3
```

Atur password admin dan secret key sebelum menjalankan:
```bash
# Windows PowerShell
$env:ADMIN_PASSWORD="ganti-dengan-password-kuat"
$env:SECRET_KEY="ganti-dengan-random-secret-panjang"
$env:DATA_DIR="data"
uvicorn app:app --reload --port 8000

# macOS/Linux
ADMIN_PASSWORD='ganti-dengan-password-kuat' SECRET_KEY='ganti-dengan-random-secret-panjang' DATA_DIR=data uvicorn app:app --reload --port 8000
```

Buka `http://localhost:8000` untuk website dan `http://localhost:8000/admin` untuk panel admin.

## Foto kopi

Foto asli dari Wikimedia Commons tersedia untuk semua 20 jenis minuman di katalog. Script download otomatis dijalankan saat startup (`start.sh`).

Untuk mengunduh manual ke folder lokal:
```bash
python scripts/download_coffee_images.py --per-class 3
```

Foto tersimpan di `data/images/<label>/` dan metadata lisensi di `data/coffee_image_metadata.csv`. Periksa ketentuan lisensi dan atribusi tiap gambar sebelum penggunaan komersial.

## Deployment ke publik (Render.com)

Project ini sudah siap deploy ke Render menggunakan Docker dengan persistent disk.

### Langkah 1: Install Git dan unggah ke GitHub

1. Download dan install [Git for Windows](https://git-scm.com/download/win)
2. Buat akun di [GitHub](https://github.com) jika belum punya
3. Buat repository baru di GitHub (private direkomendasikan)
4. Buka terminal/PowerShell di folder `pikopikopi/`:
   ```powershell
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin https://github.com/<username>/<repo-name>.git
   git branch -M main
   git push -u origin main
   ```

### Langkah 2: Deploy ke Render.com

1. Buat akun di [Render.com](https://render.com) (gratis tier tersedia)
2. Klik **New → Web Service**
3. Hubungkan ke repository GitHub yang baru dibuat
4. Pilih **Runtime: Docker**
5. Render akan otomatis mendeteksi `Dockerfile` dan konfigurasi dari `render.yaml`

### Langkah 3: Konfigurasi environment variables

Di dashboard Render, buka tab **Environment** dan tambahkan:

| Key | Value |
|-----|-------|
| `ADMIN_PASSWORD` | Password kuat untuk akses admin (min. 12 karakter) |
| `SECRET_KEY` | String random panjang (bisa generate di [random.org](https://www.random.org/strings/)) |
| `COOKIE_SECURE` | `1` |
| `DATA_DIR` | `/var/data` (sudah ada di render.yaml, tidak perlu ubah) |

### Langkah 4: Konfigurasi persistent disk

Di tab **Disks**, pastikan disk sudah dikonfigurasi:
- Name: `pikopikopi-data`
- Mount Path: `/var/data`
- Size: 1 GB

> **Catatan:** Persistent disk hanya tersedia di Render paid plan (mulai Starter $7/bulan). Free tier tidak mendukung persistent disk — data akan hilang setelah restart.

### Langkah 5: Deploy

1. Klik **Deploy**
2. Tunggu build selesai (3–5 menit pertama kali)
3. Saat first run, `start.sh` akan otomatis mengunduh foto kopi dari Wikimedia Commons ke `/var/data/images/`
4. Health check `/api/health` akan green setelah server siap
5. Website dapat diakses di URL yang diberikan Render (format: `https://<service-name>.onrender.com`)

### Langkah 6: Domain kustom (opsional)

Di tab **Settings → Custom Domains**, tambahkan domain milikmu dan ikuti instruksi DNS yang diberikan.

### Troubleshooting deployment

- **Build gagal**: Pastikan tidak ada file besar di repo. Cek log build di Render dashboard.
- **Foto tidak muncul**: Lihat log startup — download mungkin gagal karena rate limit Wikimedia. Jalankan ulang atau upload manual via panel admin.
- **Admin tidak bisa login**: Pastikan `ADMIN_PASSWORD` sudah di-set di environment variables.
- **Data hilang setelah restart**: Pastikan persistent disk terpasang di mount path `/var/data`.

## Logika rekomendasi dan batas dataset

- Survei memuat 4.042 respons, pilihan karakter rasa, preferensi kekuatan dan roast, serta penilaian bitterness/acidity/preference untuk sampel A–D.
- Profil bitterness, acidity, strength, roast, body, dan tag rasa untuk masing-masing jenis minuman pada `catalog.json` adalah estimasi karakter umum untuk prototipe.
- Skor "% cocok" merupakan skor pencocokan heuristik, bukan akurasi model machine learning yang telah divalidasi.

## Dashboard admin

1. Buka `/admin` dan masuk memakai nilai `ADMIN_PASSWORD` di environment server.
2. Tambah banner sponsor, judul, deskripsi, URL tujuan, gambar opsional, dan kata kunci yang dipisahkan dengan koma.
3. Banner hanya muncul ketika pencarian pengunjung memuat salah satu kata kunci aktif.
4. Gunakan bagian Dataset untuk mengganti file survei dengan CSV berformat sama.
5. Gunakan bagian Foto Kopi untuk mengunggah foto tambahan berdasarkan jenis minuman.
