"""Add album covers to posts that name a release (layout B, picked 5 Nov 2026).

Layout: date and title, then the cover at full content width, then the text.
Posts with no cover found stay as they are (no placeholder).

Reads docs/missing_covers.csv (rows with a cover_source_url, from
scripts/cover_lookup.py), minus any post listed in docs/covers_rejected.txt
(one post_path per line: covers Mersenne marked wrong).

For each post, in place:
  - downloads the cover once to assets/covers/<era>-<year>-<slug>.jpg
    (1200 px when the source has it), so the site never hotlinks;
  - inserts <figure class="post-cover"> right after the post header;
  - sets "cover" on the post in archive/posts.json or tumblr/posts.json.
Running it twice changes nothing. build_posts.py is NOT used.

  python3 scripts/covers_add.py --dry-run
  python3 scripts/covers_add.py
"""
import csv
import html
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'assets' / 'covers'
HEADER_END = re.compile(r'(<div class="post-header">.*?</h1>\s*</div>)(\s*)', re.S)
UA = {'User-Agent': 'undomondo-covers/1.0 (+https://www.undomondo.com)'}


def big(url):
    """Ask for the 1200 px version first, then the URL as found."""
    if 'coverartarchive.org' in url:
        return [re.sub(r'front-\d+$', 'front-1200', url), url]
    if 'mzstatic.com' in url:
        return [re.sub(r'/\d+x\d+bb\.jpg$', '/1200x1200bb.jpg', url), url]
    return [url]


def fetch(url, dest):
    for u in big(url):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30) as r:
                data = r.read()
            if len(data) > 5000 and data[:3] == b'\xff\xd8\xff':
                dest.write_bytes(data)
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def size(path):
    """(width, height) of a JPEG, read from its header."""
    b = path.read_bytes()
    i = 2
    while i < len(b):
        if b[i] != 0xFF:
            i += 1
            continue
        mark = b[i + 1]
        if mark in (0xC0, 0xC1, 0xC2):
            return int.from_bytes(b[i + 7:i + 9], 'big'), int.from_bytes(b[i + 5:i + 7], 'big')
        i += 2 + int.from_bytes(b[i + 2:i + 4], 'big')
    return 1200, 1200


def load(era):
    p = ROOT / era / 'posts.json'
    raw = p.read_text(encoding='utf-8')
    return p, raw, json.loads(raw)


def main():
    dry = '--dry-run' in sys.argv
    rej_file = ROOT / 'docs' / 'covers_rejected.txt'
    rejected = set(rej_file.read_text().split()) if rej_file.exists() else set()
    rows = [r for r in csv.DictReader(open(ROOT / 'docs' / 'missing_covers.csv', encoding='utf-8'))
            if r['cover_source_url'] and r['post_path'] not in rejected]

    data = {e: load(e) for e in ('archive', 'tumblr')}
    tmap = {v: k for k, v in json.loads((ROOT / 'tumblr' / 'urlmap.json').read_text()).items()}
    index = {}
    for p in data['archive'][2]:
        index[f"/archive/{str(p['date'])[:4]}/{p['slug']}.html"] = p
    tid = {str(p['id']): p for p in data['tumblr'][2]}
    for path, i in tmap.items():
        if i in tid:
            index[path] = tid[i]

    OUT.mkdir(parents=True, exist_ok=True)
    done = skipped = 0
    for r in rows:
        path = r['post_path']
        era = 'archive' if path.startswith('/archive/') else 'tumblr'
        page = ROOT / path.lstrip('/')
        post = index.get(path)
        if not page.exists() or post is None:
            print('no page or no posts.json entry, skipped:', path); skipped += 1; continue
        year, slug = page.parent.name, page.stem
        rel = f'/assets/covers/{era}-{year}-{slug}.jpg'
        img = ROOT / rel.lstrip('/')
        html_text = page.read_text(encoding='utf-8')
        if 'class="post-cover"' in html_text:
            continue
        m = HEADER_END.search(html_text)
        if not m:
            print('no post header, skipped:', path); skipped += 1; continue
        if not dry and not img.exists() and not fetch(r['cover_source_url'], img):
            print('download failed, skipped:', path); skipped += 1; continue
        w, h = size(img) if img.exists() else (1200, 1200)
        cap = f' style="max-width:{w}px"' if w < 600 else ''   # small scans: no blurry upscale
        alt = html.escape(f"{r['artist']} – {r['release_title']} cover", quote=True)
        fig = f'\n        <figure class="post-cover"><img src="{rel}" alt="{alt}" width="{w}" height="{h}"{cap}></figure>'
        print('cover  ', path)
        done += 1
        if dry:
            continue
        page.write_text(html_text[:m.end(1)] + fig + html_text[m.end(1):], encoding='utf-8')
        post['cover'] = rel

    if not dry and done:
        for era, (p, raw, posts) in data.items():
            ind = 1 if era == 'tumblr' else None
            p.write_text(json.dumps(posts, ensure_ascii=False, indent=ind), encoding='utf-8')
    print(f'\n{done} covers added, {skipped} skipped')


if __name__ == '__main__':
    main()
