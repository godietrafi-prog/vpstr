"""
Convert any PDF in media/ that lacks a matching JPG into a portrait-ready JPEG,
add it to slides.json pool, then report what changed.

Usage:
    python3 scripts/process_posters.py

Run from the repo root. Requires pymupdf (already installed).
"""

import json
import os
import sys
import pymupdf  # PyMuPDF

MEDIA_DIR  = "media"
SLIDES_JSON = "slides.json"

# Target dimensions for portrait TV (1080×1920 = Full HD vertical)
TARGET_W = 1080
TARGET_H = 1920


def pdf_to_jpg(pdf_path: str, jpg_path: str) -> bool:
    """Render first page of PDF to a portrait-fit JPEG. Returns True on success."""
    try:
        doc  = pymupdf.open(pdf_path)
        page = doc[0]

        # Scale so the page fills TARGET_W width at 150 dpi-equivalent
        rect = page.rect
        scale = TARGET_W / rect.width
        mat   = pymupdf.Matrix(scale, scale)
        pix   = page.get_pixmap(matrix=mat, alpha=False)

        pix.save(jpg_path)
        doc.close()
        print(f"  ✓ {os.path.basename(pdf_path)} → {os.path.basename(jpg_path)}"
              f"  ({pix.width}×{pix.height})")
        return True
    except Exception as e:
        print(f"  ✗ {os.path.basename(pdf_path)}: {e}", file=sys.stderr)
        return False


def load_slides():
    with open(SLIDES_JSON, encoding="utf-8") as f:
        return json.load(f)


def save_slides(data):
    with open(SLIDES_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def pool_srcs(data) -> set:
    pool = data.get("pool") or data
    return {s.get("src", "") for s in pool if isinstance(s, dict)}


def add_to_pool(data, src: str):
    entry = {"src": src, "type": "poster"}
    if isinstance(data, dict) and "pool" in data:
        data["pool"].append(entry)
    elif isinstance(data, list):
        data.append(entry)
    else:
        data["pool"] = data.get("pool", []) + [entry]


def main():
    if not os.path.isdir(MEDIA_DIR):
        sys.exit(f"ERROR: '{MEDIA_DIR}' directory not found. Run from repo root.")

    pdfs = sorted(
        f for f in os.listdir(MEDIA_DIR)
        if f.lower().endswith(".pdf")
    )

    if not pdfs:
        print("No PDFs found in media/.")
        return

    data         = load_slides()
    existing_srcs = pool_srcs(data)
    added        = []

    for pdf_name in pdfs:
        base     = os.path.splitext(pdf_name)[0]
        jpg_name = base + ".jpg"
        jpg_path = os.path.join(MEDIA_DIR, jpg_name)
        pdf_path = os.path.join(MEDIA_DIR, pdf_name)
        src      = f"{MEDIA_DIR}/{jpg_name}"

        # Skip if JPG already exists AND already in pool
        if os.path.exists(jpg_path) and src in existing_srcs:
            print(f"  — {pdf_name}: already processed, skipping")
            continue

        # Convert PDF → JPG if JPG missing
        if not os.path.exists(jpg_path):
            ok = pdf_to_jpg(pdf_path, jpg_path)
            if not ok:
                continue

        # Add to pool if not already there
        if src not in existing_srcs:
            add_to_pool(data, src)
            added.append(src)
            print(f"  + Added to pool: {src}")
        else:
            print(f"  — {jpg_name}: already in pool")

    if added:
        save_slides(data)
        print(f"\nslides.json updated — {len(added)} new poster(s) added.")
        print("Next: git add media/ slides.json && git commit -m 'feat: add new poster(s)' && git push")
    else:
        print("\nNothing new to add.")


if __name__ == "__main__":
    main()
