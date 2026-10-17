"""Point old archive posts' dead mp3 links at the copies on Cloudflare R2.

Edits archive/posts.json (the source) and the matching archive/{year}/{slug}.html
page in place. build_posts.py isn't used: on 2026-10-18 a full rebuild no longer
matched the live pages (it dropped Tumblr embeds and restored removed posts).

Each matched link becomes an inline stream-only player. Unmatched links are
left alone. Sure matches are used, and _check/ matches whose old link was named
artist--title.mp3 (Mersenne, 2026-10-18: those are right). Matches guessed from
the post title alone are left out.

  python3 scripts/mp3_relink.py jamie-saft-trio-plays-bob-dylan   # one post
  python3 scripts/mp3_relink.py --all                             # every post with a sure match
  python3 scripts/mp3_relink.py --all --archive-org               # also unmatched archive.org links still up
"""
import csv
import html
import json
import re
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

R2 = 'https://pub-74f32648a39b49f2b7715a1cd04c1501.r2.dev/posts/'
MANIFEST = Path.home() / 'Music/undomondo-mp3s/manifest.csv'
ARCHIVE = Path(__file__).resolve().parent.parent / 'archive'
POSTS = ARCHIVE / 'posts.json'

PLAYER = ('<audio controls preload="none" controlslist="nodownload" src="{src}" '
          'style="display:block;width:100%;max-width:420px;height:32px;margin:6px 0 10px;"></audio>')


def sure(r):
    """Sure matches, plus _check matches whose old link was named artist--title.
    Matches guessed from the post title alone are never used."""
    if not r['new_file'] or r['how'] == 'loose: from the post title':
        return False
    if not r['new_file'].startswith('_check/'):
        return True
    name = urllib.parse.unquote(r['old_url'].rsplit('/', 1)[-1])
    return '--' in name


def alive(url):
    """True if archive.org still serves the file (a one-byte request)."""
    req = urllib.request.Request(url, headers={'Range': 'bytes=0-0', 'User-Agent': 'undomondo-relink'})
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            return res.status in (200, 206)
    except Exception:
        return False


def archive_org_rows(rows):
    """Unmatched archive.org links (mostly netlabel releases) that still play,
    pointed at their https address instead of a copy on R2."""
    todo = [r for r in rows if not r['new_file'] and 'archive.org/' in r['old_url']]
    for r in todo:
        r['src'] = 'https://archive.org/' + r['old_url'].split('archive.org/', 1)[1]
    with ThreadPoolExecutor(10) as pool:
        ok = list(pool.map(lambda r: alive(r['src']), todo))
    print(f"archive.org: {sum(ok)} of {len(todo)} links still up")
    return [r for r, good in zip(todo, ok) if good]


def relink(text, rows):
    done = 0
    for r in rows:
        src = r.get('src') or R2 + urllib.parse.quote(r['new_file'])
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
    every = list(csv.DictReader(open(MANIFEST)))
    rows = [r for r in every if sure(r)]
    if '--archive-org' in sys.argv:
        rows += archive_org_rows(every)
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
