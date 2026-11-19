# Coffee Image Dataset Builder (100 images)

Target: 20 coffee-drink classes x 5 photos each = 100 images.

## Classes
- `espresso` — Espresso (5 images)
- `americano` — Americano (5 images)
- `cappuccino` — Cappuccino (5 images)
- `caffe_latte` — Caffe Latte (5 images)
- `mocha` — Caffe Mocha (5 images)
- `flat_white` — Flat White (5 images)
- `macchiato` — Macchiato (5 images)
- `latte_macchiato` — Latte Macchiato (5 images)
- `cortado` — Cortado (5 images)
- `affogato` — Affogato (5 images)
- `ristretto` — Ristretto (5 images)
- `lungo` — Lungo (5 images)
- `cafe_au_lait` — Cafe au Lait (5 images)
- `cafe_bombon` — Cafe Bombon (5 images)
- `cafe_con_leche` — Cafe con Leche (5 images)
- `vietnamese_iced_coffee` — Vietnamese Iced Coffee (5 images)
- `cold_brew` — Cold Brew (5 images)
- `iced_coffee` — Iced Coffee (5 images)
- `blended_coffee` — Frappuccino / Blended Coffee (5 images)
- `irish_coffee` — Irish Coffee (5 images)

## Build dataset
1. Install Python 3.9+.
2. Install dependency: `pip install requests`
3. Run: `python download_dataset.py`
4. Image files will be stored in `images/<class>/`.
5. Attribution and license metadata is recorded in `metadata.csv`.

The downloader queries Wikimedia Commons and downloads thumbnail images where available.
It may not reach 5 images for every class in one run; run again or supplement manually.
Always inspect the image and license metadata. License conditions differ by file; some require
attribution, share-alike, or other conditions. This is a dataset for research/education,
not a guarantee that every image is appropriate for commercial use.

Suggested train/validation/test split after collection:
- Train: 70% (3-4 images per class, but target dataset is too small for robust training)
- Validation: 15%
- Test: 15%

For better ML performance, expand to at least 100-500 images per class and avoid near-duplicates.
