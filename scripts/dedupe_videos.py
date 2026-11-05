"""Remove the second copy of a YouTube video from old posts.

Many post pages show the same video twice: the site's own player at the top
of the post (<div class="embed-wrap"> with a youtube-nocookie iframe), then
the old raw <iframe src="https://www.youtube.com/embed/..."> from the original
post further down. This removes the raw one, but only when its video id is
exactly the id of a player at the top. Different ids: both stay.

Edits the source JSON and the matching static page together, in place, like
scripts/mp3_relink.py and scripts/autop.py. build_posts.py is NOT used (see
cloud-desk task 02: a full rebuild breaks live pages).

posts.json holds only the raw iframe; the top player exists only on the page.
So in posts.json the raw iframe is swapped for the page's exact top player,
put at the start of the post. The video stays in the source, and the source
then matches what the page shows.

  python3 scripts/dedupe_videos.py --survey                  # counts only
  python3 scripts/dedupe_videos.py archive SLUG [SLUG ...]   # by slug
  python3 scripts/dedupe_videos.py archive --all             # every affected post
  python3 scripts/dedupe_videos.py tumblr --all              # Tumblr, by id / --all
  add --dry-run to print what would change without writing
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
START = '<div class="post-content">'
END = re.compile(r'</div>\n\s*<div class="post-(?:tags|nav)">')
WRAP = re.compile(r'\s*(<div class="embed-wrap[^"]*"><iframe\b[^>]*></iframe></div>)')
TOP_ID = re.compile(r'youtube-nocookie\.com/embed/([A-Za-z0-9_-]{11})')
RAW = re.compile(r'<iframe\b[^>]*\bsrc="https?://(?:www\.)?youtube(?:-nocookie)?\.com/embed/'
                 r'([A-Za-z0-9_-]{11})[^"]*"[^>]*>\s*</iframe>', re.I)


def split_body(body):
    """(top players as [(id, markup)], index where the rest of the body starts)."""
    pos, top = 0, []
    while True:
        m = WRAP.match(body, pos)
        if not m:
            return top, pos
        t = TOP_ID.search(m.group(1))
        if t:
            top.append((t.group(1), m.group(1)))
        pos = m.end()


def dupes(body):
    """Raw iframes after the top players whose id matches a top player."""
    top, rest = split_body(body)
    ids = {i for i, _ in top}
    return top, [m for m in RAW.finditer(body, rest) if m.group(1) in ids]


def cut(text, raw):
    """Remove one raw iframe string, plus a <p>/<center> left empty around it,
    and close the blank-line gap it leaves."""
    i = text.find(raw)
    if i < 0:
        return None
    a, b = i, i + len(raw)
    pre = re.search(r'<(p|center)>\s*$', text[:a])
    post = re.match(r'\s*</(p|center)>', text[b:])
    if pre and post and pre.group(1) == post.group(1):
        a, b = pre.start(), b + post.end()
    head, tail = text[:a].rstrip(' \t\r\n'), text[b:].lstrip(' \t\r\n')
    if not head:
        return tail
    if not tail:
        return head
    return head + '\n\n' + tail


def page_for(era, post, urlmap):
    if era == 'archive':
        return ROOT / 'archive' / str(post['year']) / f"{post['slug']}.html"
    p = urlmap.get(str(post['id']))
    return ROOT / p.lstrip('/') if p else None


def load(era):
    posts = json.loads((ROOT / era / 'posts.json').read_text(encoding='utf-8'))
    urlmap = json.loads((ROOT / era / 'urlmap.json').read_text(encoding='utf-8')) if era == 'tumblr' else {}
    return posts, urlmap


def page_body(html):
    i = html.find(START)
    m = END.search(html, i) if i >= 0 else None
    if i < 0 or not m:
        return None
    return i + len(START), m.start()


def fix(post, page, dry):
    """Returns (status, number of embeds removed). Page and JSON change together or not at all."""
    html = page.read_text(encoding='utf-8')
    span = page_body(html)
    if not span:
        return 'no post-content block', 0
    a, z = span
    body = html[a:z]
    top, found = dupes(body)
    if not found:
        return 'no duplicates', 0
    new_body, content = body, post['content']
    removed = []
    for m in found:
        raw = m.group(0)
        if raw not in content:
            return 'raw embed not in posts.json, skipped', 0
        new_body = cut(new_body, raw)
        content = cut(content, raw)
        if new_body is None or content is None:
            return 'could not cut, skipped', 0
        removed.append(m.group(1))
    # keep each removed video in posts.json as the page's own top player
    players = [mk for i, mk in top if i in removed and mk not in content]
    if players:
        content = ''.join(players) + '\n\n' + content.lstrip()
    if not dry:
        page.write_text(html[:a] + new_body + html[z:], encoding='utf-8')
        post['content'] = content
    return 'fixed', len(removed)


def survey():
    for era in ('archive', 'tumblr'):
        posts, urlmap = load(era)
        pages = embeds = different = 0
        for post in posts:
            page = page_for(era, post, urlmap)
            if not page or not page.exists():
                continue
            html = page.read_text(encoding='utf-8')
            span = page_body(html)
            if not span:
                continue
            body = html[span[0]:span[1]]
            top, found = dupes(body)
            ids = {i for i, _ in top}
            others = [m for m in RAW.finditer(body, split_body(body)[1]) if m.group(1) not in ids]
            if found:
                pages += 1
                embeds += len(found)
            if others:
                different += 1
        print(f'{era}: {pages} pages with a duplicate video ({embeds} raw embeds to remove); '
              f'{different} pages with a raw YouTube embed whose id is not in the top player (left alone)')


def main():
    args = sys.argv[1:]
    if '--survey' in args:
        return survey()
    dry = '--dry-run' in args
    era = args[0]
    want = None if '--all' in args else {a for a in args[1:] if not a.startswith('-')}
    posts, urlmap = load(era)
    n = total = 0
    for post in posts:
        key = post['slug'] if era == 'archive' else str(post['id'])
        if want is not None and key not in want:
            continue
        page = page_for(era, post, urlmap)
        if not page or not page.exists():
            continue
        status, k = fix(post, page, dry)
        if status == 'no duplicates':
            continue
        print(f'{status:>10} ({k}): {page.relative_to(ROOT)}')
        if status == 'fixed':
            n += 1
            total += k
    if not dry and n:
        indent = 1 if era == 'tumblr' else None   # keep each file's own layout
        (ROOT / era / 'posts.json').write_text(json.dumps(posts, ensure_ascii=False, indent=indent), encoding='utf-8')
    print(f"{n} page(s), {total} embed(s) {'would be removed' if dry else 'removed'}")


if __name__ == '__main__':
    main()
