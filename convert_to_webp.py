#!/usr/bin/env python3
"""
convert_to_webp.py
==================
Converts every JPEG / PNG image in posts/images/ to WebP, updates all
references in .md posts, index.json, and HTML files, then regenerates
posts-data.js and the social-sharing pages.

Run from the profile directory:
    python3 convert_to_webp.py

Options (edit the constants below):
    WEBP_QUALITY  - 0-100  (82 is a great quality/size balance)
    DELETE_ORIGINALS - True to remove the original .jpg/.png files after conversion
"""

import os, re, json, sys, subprocess
from pathlib import Path

# ── Configuration ────────────────────────────────────────────────────────────
PROFILE_DIR      = Path(__file__).resolve().parent
IMAGES_DIR       = PROFILE_DIR / 'posts' / 'images'
WEBP_QUALITY     = 82
DELETE_ORIGINALS = True
# ─────────────────────────────────────────────────────────────────────────────

try:
    from PIL import Image
except ImportError:
    print("Installing Pillow...")
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'Pillow', '-q'])
    from PIL import Image


def convert_images():
    """Convert JPEG/PNG files to WebP. Returns {old_filename: new_filename}."""
    mapping = {}
    total_before = total_after = 0
    SOURCE_EXTS = {'.jpg', '.jpeg', '.png', '.gif'}

    for src in sorted(IMAGES_DIR.iterdir()):
        if src.suffix.lower() not in SOURCE_EXTS:
            continue
        dst = src.with_suffix('.webp')
        if dst.exists():
            mapping[src.name] = dst.name
            print(f'  skip (exists)  {src.name}')
            continue

        size_before = src.stat().st_size
        try:
            with Image.open(src) as im:
                if im.mode in ('RGBA', 'LA', 'P'):
                    im = im.convert('RGB')
                im.save(dst, 'WEBP', quality=WEBP_QUALITY, method=6)
            size_after = dst.stat().st_size
            saved_pct  = 100 * (size_before - size_after) / size_before
            print(f'  {src.name:55s}  '
                  f'{size_before//1024:>4}KB -> {size_after//1024:>4}KB  '
                  f'-{saved_pct:.0f}%')
            total_before += size_before
            total_after  += size_after
            mapping[src.name] = dst.name
        except Exception as exc:
            print(f'  ERROR {src.name}: {exc}')

    if total_before:
        saved_total = 100 * (total_before - total_after) / total_before
        print(f'\n  TOTAL  {total_before//1024}KB -> {total_after//1024}KB  '
              f'  -{saved_total:.0f}%  '
              f'  ({(total_before-total_after)//1024}KB saved)')
    return mapping


def delete_originals(mapping):
    for old in mapping:
        old_path = IMAGES_DIR / old
        if old_path.exists() and old_path.suffix.lower() != '.webp':
            old_path.unlink()
            print(f'  removed  {old}')


def update_file(path, mapping):
    """Replace all old filenames with new ones in a text file."""
    text = path.read_text(encoding='utf-8')
    updated = text
    for old, new in mapping.items():
        updated = updated.replace(old, new)
    if updated != text:
        path.write_text(updated, encoding='utf-8')
        return True
    return False


def update_references(mapping):
    changed = 0
    # .md posts
    for f in sorted((PROFILE_DIR / 'posts').glob('*.md')):
        if update_file(f, mapping): changed += 1
    # index.json
    if update_file(PROFILE_DIR / 'posts' / 'index.json', mapping): changed += 1
    # HTML files in profile root
    for f in sorted(PROFILE_DIR.glob('*.html')):
        if update_file(f, mapping): changed += 1
    # HTML files in posts/
    for f in sorted((PROFILE_DIR / 'posts').glob('*.html')):
        if update_file(f, mapping): changed += 1
    print(f'  {changed} file(s) updated')


def regen_posts_data():
    """Regenerate posts/posts-data.js from .md files."""
    script = Path('/tmp/gen_posts_data.py')
    if not script.exists():
        # Inline the generator so the tool is self-contained
        script.write_text(r"""
import json, os, re
posts_dir   = '/home/liviyo/Documents/job/jobs_one/profile/posts'
output_file = os.path.join(posts_dir, 'posts-data.js')

def parse_frontmatter(text):
    fm = {}
    if not text.startswith('---'):
        return fm, text
    end = text.index('---', 3)
    block = text[3:end].strip()
    body  = text[end+3:].strip()
    for line in block.split('\n'):
        colon = line.find(':')
        if colon == -1: continue
        key = line[:colon].strip()
        val = line[colon+1:].strip()
        fm['tags'] = [t.strip() for t in val.split(',')] if key == 'tags' else None
        if key != 'tags': fm[key] = val
    return fm, body

data = {}
for fname in sorted(os.listdir(posts_dir)):
    if not fname.endswith('.md'): continue
    pid = fname[:-3]
    text = open(os.path.join(posts_dir, fname), encoding='utf-8').read()
    fm, body = parse_frontmatter(text)
    data[pid] = {'fm': fm, 'body': body}

js = 'window.POSTS_DATA = ' + json.dumps(data, ensure_ascii=False, indent=2) + ';\n'
open(output_file, 'w', encoding='utf-8').write(js)
print(f'Generated {len(data)} posts')
""", encoding='utf-8')

    result = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
    print(f'  {result.stdout.strip()}')
    if result.returncode != 0:
        print(f'  WARNING: {result.stderr}')


def regen_post_pages():
    """Regenerate individual social-sharing HTML pages."""
    script = PROFILE_DIR / 'gen_post_pages.py'
    if script.exists():
        result = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
        lines = result.stdout.strip().split('\n')
        print(f'  {lines[-1] if lines else "done"}')
    else:
        print('  gen_post_pages.py not found — skipping page regeneration')


def main():
    print('=' * 60)
    print(' WebP Converter — Halalisani Ngema Blog')
    print('=' * 60)

    print('\n1. Converting images...')
    mapping = convert_images()
    if not mapping:
        print('   No images found to convert.')
        return

    if DELETE_ORIGINALS:
        print('\n2. Removing originals...')
        delete_originals(mapping)

    print('\n3. Updating all file references...')
    update_references(mapping)

    print('\n4. Regenerating posts-data.js...')
    regen_posts_data()

    print('\n5. Regenerating social-sharing pages...')
    regen_post_pages()

    print('\n' + '=' * 60)
    print(' Done! Run this script again whenever you add new images.')
    print(' IMPORTANT: For Facebook og:image previews to work, you must')
    print(' host the site on a real domain. Once deployed, open each')
    print(' post HTML file (e.g. 2026-04-22-job-hunting-strategy.html)')
    print(' and replace  og:image content="posts/images/..."')
    print(' with         og:image content="https://yourdomain.com/posts/images/..."')
    print(' Or run:  sed -i "s|og:image\" content=\"|og:image\" content=\"https://yourdomain.com/|g" *.html')
    print('=' * 60)


if __name__ == '__main__':
    main()
