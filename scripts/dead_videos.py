"""Remove YouTube players whose video is gone from the old WordPress posts.

A video counts as gone when YouTube's oembed answers anything but 200:
404 deleted, 403 private, 401 embedding switched off by the owner. None of
these play on the site.

Removes, from the page AND archive/posts.json together, in place:
  - the site's own player: <div class="embed-wrap"><iframe ...youtube...></iframe></div>
  - a raw <iframe src="...youtube.com/embed/ID"></iframe> left from the old post
Plain text links to YouTube stay (they belong to the dead-link report).
build_posts.py is NOT used, same as mp3_relink.py / autop.py / dedupe_videos.py.

  python3 scripts/dead_videos.py --check     # ask YouTube, write docs/dead_videos.txt
  python3 scripts/dead_videos.py --dry-run   # print what would change
  python3 scripts/dead_videos.py             # apply
"""
import json
import re
import sys
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIST = ROOT / 'docs' / 'dead_videos.txt'
ID = r'([A-Za-z0-9_-]{11})'
WRAP = re.compile(r'<div class="embed-wrap[^"]*">\s*<iframe\b[^>]*youtube(?:-nocookie)?\.com/embed/' + ID +
                  r'[^>]*>\s*</iframe>\s*</div>', re.I)
RAW = re.compile(r'<iframe\b[^>]*\bsrc="https?://(?:www\.)?youtube(?:-nocookie)?\.com/embed/' + ID +
                 r'[^"]*"[^>]*>\s*</iframe>', re.I)
ANY = re.compile(r'youtube(?:-nocookie)?\.com/embed/' + ID)


def status(vid):
    url = f'https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={vid}&format=json'
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return 0            # network trouble: never treated as dead


def pages():
    return sorted((ROOT / 'archive').glob('20*/*.html'))


def check():
    ids = sorted({i for p in pages() for i in ANY.findall(p.read_text(encoding='utf-8'))})
    with ThreadPoolExecutor(8) as ex:
        res = dict(zip(ids, ex.map(status, ids)))
    dead = {i: s for i, s in res.items() if s in (401, 403, 404)}
    LIST.write_text(''.join(f'{i} {s}\n' for i, s in sorted(dead.items())), encoding='utf-8')
    print(f'{len(ids)} videos, {len(dead)} gone, {sum(1 for s in res.values() if s == 0)} unreachable (kept)')


def cut(text, dead):
    """Remove dead players; drop a <p>/<center> left empty and tidy the gap."""
    n = 0
    for rx in (WRAP, RAW):
        def rep(m):
            nonlocal n
            if m.group(1) in dead:
                n += 1
                return ''
            return m.group(0)
        text = rx.sub(rep, text)
    text = re.sub(r'<(p|center)>\s*</\1>', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text, n


def main():
    if '--check' in sys.argv:
        return check()
    dry = '--dry-run' in sys.argv
    dead = {l.split()[0] for l in LIST.read_text().splitlines() if l.strip()}
    jpath = ROOT / 'archive' / 'posts.json'
    raw_json = jpath.read_text(encoding='utf-8')
    posts = json.loads(raw_json)
    by_page = {f"{str(p['date'])[:4]}/{p['slug']}": p for p in posts}
    total = touched = emptied = skipped = 0
    for page in pages():
        html = page.read_text(encoding='utf-8')
        a = html.find('<div class="post-content">')
        z = re.compile(r'</div>\n\s*<div class="post-(?:tags|nav)">').search(html, a)
        if a < 0 or not z:
            continue
        a += len('<div class="post-content">')
        body = html[a:z.start()]
        new_body, n = cut(body, dead)
        if not n:
            continue
        post = by_page.get(f'{page.parent.name}/{page.stem}')
        if not post:
            skipped += 1
            print('no posts.json entry, skipped:', page.relative_to(ROOT))
            continue
        new_content, m = cut(post['content'], dead)
        # m < n: some players were built from a plain link and lives only on the
        # page; posts.json has nothing to remove, so the page alone changes.
        if m > n:
            skipped += 1
            print(f'page/json differ ({n} vs {m}), skipped:', page.relative_to(ROOT))
            continue
        total += n
        touched += 1
        if not ANY.search(new_body):
            emptied += 1
        print(f'{n} removed  {page.relative_to(ROOT)}')
        if not dry:
            page.write_text(html[:a] + new_body + html[z.start():], encoding='utf-8')
            if m:
                post['content'] = new_content
    if not dry and touched:
        ind = 1 if raw_json.startswith('[\n') else None
        jpath.write_text(json.dumps(posts, ensure_ascii=False, indent=ind), encoding='utf-8')
    print(f'\n{total} players removed on {touched} posts; {emptied} posts now have no video; {skipped} skipped')


if __name__ == '__main__':
    main()
