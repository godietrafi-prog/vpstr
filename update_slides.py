"""
update_slides.py  —  Poster Viewers
====================================
הפעלה רגילה (פעם אחת):
    python update_slides.py

מצב watch — מריץ ברקע, מגיב אוטומטית לקבצים חדשים ב-media/:
    python update_slides.py --watch

מה הסקריפט עושה:
  1. ממיר כל PDF חדש ב-media/ ל-JPG (עמוד ראשון, רזולוציה גבוהה).
     PDF שכבר יש לו JPG — מדולג.
  2. בונה מחדש את slides.json מכל הקבצים ב-media/.

זיהוי סוג לפי שם קובץ:
  - מכיל "poster" (אותיות גדולות/קטנות)  → poster
  - mp4 / webm / mov / ogg               → video
  - כל שאר התמונות                       → image

סרטונים: יש להעביר דרך process_video.bat לפני ההוספה.
"""

import os, json, subprocess, sys, time

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
MEDIA_DIR   = os.path.join(BASE_DIR, 'media')
SLIDES_JSON = os.path.join(BASE_DIR, 'slides.json')

IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
VIDEO_EXTS = {'.mp4', '.webm', '.mov', '.ogg'}
SKIP_FILES = {'.gitkeep', 'desktop.ini'}


def get_type(filename):
    ext = os.path.splitext(filename)[1].lower()
    if ext in VIDEO_EXTS:
        return 'video'
    if 'poster' in filename.lower():
        return 'poster'
    return 'image'


def ensure_pymupdf():
    try:
        import fitz
        return fitz
    except ImportError:
        print("  Installing PyMuPDF...")
        flags = ['--quiet']
        # on Debian/Ubuntu system Python, need --break-system-packages
        try:
            subprocess.check_call(
                [sys.executable, '-m', 'pip', 'install', 'pymupdf'] + flags,
                stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError:
            subprocess.check_call(
                [sys.executable, '-m', 'pip', 'install', 'pymupdf',
                 '--break-system-packages'] + flags)
        import fitz
        return fitz


def convert_pdfs():
    """Convert any PDF in media/ that has no matching JPG yet."""
    fitz = ensure_pymupdf()
    converted = []
    for filename in sorted(os.listdir(MEDIA_DIR)):
        if not filename.lower().endswith('.pdf'):
            continue
        jpg_name = os.path.splitext(filename)[0] + '.jpg'
        jpg_path = os.path.join(MEDIA_DIR, jpg_name)
        if os.path.exists(jpg_path):
            continue
        pdf_path = os.path.join(MEDIA_DIR, filename)
        try:
            doc = fitz.open(pdf_path)
            pix = doc[0].get_pixmap(matrix=fitz.Matrix(2.5, 2.5))
            pix.save(jpg_path)
            doc.close()
            print(f"  PDF→JPG: {jpg_name}  ({pix.width}×{pix.height})")
            converted.append(jpg_name)
        except Exception as e:
            print(f"  ERROR: {filename}: {e}")
    return converted


def update_slides_json():
    """Rebuild slides.json from every image/video in media/."""
    pool = []
    for filename in sorted(os.listdir(MEDIA_DIR)):
        if filename in SKIP_FILES or filename.startswith('.'):
            continue
        ext = os.path.splitext(filename)[1].lower()
        if ext not in IMAGE_EXTS and ext not in VIDEO_EXTS:
            continue
        pool.append({'src': f'media/{filename}', 'type': get_type(filename)})

    with open(SLIDES_JSON, 'w', encoding='utf-8') as f:
        json.dump({'pool': pool}, f, ensure_ascii=False, indent=2)

    counts = {}
    for item in pool:
        counts[item['type']] = counts.get(item['type'], 0) + 1
    summary = ', '.join(f"{n} {t}" for t, n in sorted(counts.items()))
    print(f"  slides.json → {len(pool)} items  ({summary})")
    return pool


def snapshot():
    """Return a set of (filename, mtime) for all files in media/."""
    result = set()
    for f in os.listdir(MEDIA_DIR):
        p = os.path.join(MEDIA_DIR, f)
        if os.path.isfile(p):
            result.add((f, os.path.getmtime(p)))
    return result


def run_once(label=""):
    if label:
        print(f"\n[{label}] Changes detected — updating...")
    print("  Converting PDFs...")
    new_jpgs = convert_pdfs()
    if not new_jpgs:
        print("  No new PDFs.")
    print("  Rebuilding slides.json...")
    update_slides_json()


def watch_mode():
    known = snapshot()
    print(f"Ready. Tracking {len(known)} files in media\\")
    print("Drop files into media\\ — they will be processed automatically.\n")
    while True:
        time.sleep(3)
        current = snapshot()
        if current != known:
            run_once(label=time.strftime("%H:%M:%S"))
            known = snapshot()   # re-snapshot after conversion (new JPGs added)
            print(f"\nReady. Now tracking {len(known)} files.\n")


if __name__ == '__main__':
    print("=" * 48)
    print("  Poster Viewers — Update Slides")
    print("=" * 48)

    if '--watch' in sys.argv:
        run_once()          # initial pass
        watch_mode()        # then loop
    else:
        run_once()
        print("\nTip: run with --watch to auto-detect new files.")
        try:
            input("Press Enter to exit...")
        except (EOFError, KeyboardInterrupt):
            pass
