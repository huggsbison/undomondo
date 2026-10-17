"""Point old archive posts' dead mp3 links at the copies on Cloudflare R2.

Edits archive/posts.json (the source) and the matching archive/{year}/{slug}.html
page in place. build_posts.py isn't used: on 2026-10-18 a full rebuild no longer
matched the live pages (it dropped Tumblr embeds and restored removed posts).

Each matched link becomes an inline stream-only player. Unmatched links are
left alone. By default only sure matches are used; the _check/ files wait
until they've been checked.

  python3 scripts/mp3_relink.py jamie-saft-trio-plays-bob-dylan   # one post
  python3 scripts/mp3_relink.py --all                             # every post with a sure match
"""
import csv
import html
import json
import re
import sys
import urllib.parse
from pathlib import Path

R2 = 'https://pub-74f32648a39b49f2b7715a1cd04c1501.r2.dev/posts/'
MANIFEST = Path.home() / 'Music/undomondo-mp3s/manifest.csv'
ARCHIVE = Path(__file__).resolve().parent.parent / 'archive'
POSTS = ARCHIVE / 'posts.json'

PLAYER = ('<audio controls preload="none" controlslist="nodownload" src="{src}" '
          'style="display:block;width:100%;max-width:420px;height:32px;margin:6px 0 10px;"></audio>')


def sure(r):
    return r['new_file'] and not r['new_file'].startswith('_check/')


def relink(text, rows):
    done = 0
    for r in rows:
        src = R2 + urllib.parse.quote(r['new_file'])
        if src in text:
            continue
        # The old link, with whatever label it had, becomes "label + player"
        pat = re.compile(r'<a href="' + re.escape(html.escape(r['old_url'], quote=True)).replace('&amp;', '(?:&amp;|&)')
                         + r'"[^>]*>(.*?)</a>', re.S)
        alt = re.compile(r'<a href="' + re.escape(r['old_url']) + r'"[^>]*>(.*?)</a>', re.S)
        m = pat.search(text) or alt.search(text)
        if not m:
            continue
        text = text[:m.start()] + m.group(1) + PLAYER.format(src=src) + text[m.end():]
        done += 1
    return text, done


def main():
    rows = [r for r in csv.DictReader(open(MANIFEST)) if sure(r)]
    want = None if '--all' in sys.argv else set(a for a in sys.argv[1:] if not a.startswith('-'))
    posts = json.loads(POSTS.read_text())
    n_posts, n_links = 0, 0
    for post in posts:
        if want is not None and post['slug'] not in want:
            continue
        mine = [r for r in rows if r['post_slug'] == post['slug'] and r['post_date'] == post['date'][:10]]
        if not mine:
            continue
        post['content'], n = relink(post['content'], mine)
        page = ARCHIVE / str(post['year']) / f"{post['slug']}.html"
        if n and page.exists():
            text, m = relink(page.read_text(), mine)
            page.write_text(text)
            if m != n:
                print(f"  page and source differ ({m} vs {n}): {page.name}")
        elif n:
            print(f"  no page for {post['slug']}")
        if n:
            n_posts += 1
            n_links += n
            print(f"{n} link(s): {post['year']}/{post['slug']}")
    POSTS.write_text(json.dumps(posts, ensure_ascii=False))
    print(f'{n_links} links in {n_posts} posts')


if __name__ == '__main__':
    main()
