"""Apply docs/tag_proposal.csv to the site, in place.

Edits, for every post whose tags change:
  - archive/posts.json and tumblr/posts.json (the source);
  - the static post page: the tag pills and the "keywords" in the hidden
    search-engine data (ld+json);
  - the year page (archive/2006.html, tumblr/2015.html ...): the card's tag
    pills, the post's entry in the embedded allPosts list, and the
    "Filter by genre" pills;
  - archive/index.html: the "574 tags" count.

build_posts.py and rewrite_year_pages.py aren't used: build_posts.py no longer
matches the live pages, and rewrite_year_pages.py calls into it.

  python3 scripts/tag_apply.py --survey     # counts only, writes nothing
  python3 scripts/tag_apply.py              # apply
"""
import csv
import html
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ERAS = {'archive': {}, 'tumblr': {'indent': 1}}     # json.dumps options that match each file

MAP = {}
for r in csv.DictReader(open(ROOT / 'docs' / 'tag_proposal.csv', encoding='utf-8')):
    MAP[r['old_tag']] = None if r['new_tag'] == 'DROP' else r['new_tag']


def remap(tags):
    out = []
    for t in tags:
        n = MAP.get(t, t)
        if n is not None and n not in out:
            out.append(n)
    return out


def spans(tags, cls='tag'):
    return ''.join(f'<span class="{cls}">{html.escape(t)}</span>' for t in tags)


def remap_span_block(block):
    """<span class="tag">x</span>... -> remapped, keeping the shown subset."""
    shown = [html.unescape(t) for t in re.findall(r'<span class="tag">([^<]*)</span>', block)]
    return spans(remap(shown))


def post_page(era, p):
    if era == 'archive':
        return ROOT / 'archive' / str(p['date'])[:4] / f"{p['slug']}.html"
    return None     # tumblr pages are found through urlmap.json


def main():
    survey = '--survey' in sys.argv
    stats = Counter()
    tumblr_urls = json.loads((ROOT / 'tumblr' / 'urlmap.json').read_text(encoding='utf-8'))
    all_tags = set()
    changed = {}                                     # (era, id) -> (old, new)
    data = {}
    for era in ERAS:
        posts = json.loads((ROOT / era / 'posts.json').read_text(encoding='utf-8'))
        data[era] = posts
        for p in posts:
            old = p.get('tags') or []
            new = remap(old)
            all_tags.update(new)
            if new != old:
                changed[(era, str(p['id']))] = (old, new)
                stats[f'{era}: posts changed'] += 1
                p['tags'] = new

    # ---- static post pages
    pages = {}
    for era, posts in data.items():
        for p in posts:
            key = (era, str(p['id']))
            if key not in changed:
                continue
            if era == 'archive':
                path = post_page(era, p)
            else:
                u = tumblr_urls.get(str(p['id']))
                path = ROOT / u.lstrip('/') if u else None
            if not path or not path.exists():
                stats[f'{era}: changed posts with no page (removed posts)'] += 1
                continue
            pages[key] = path
            src = path.read_text(encoding='utf-8')
            old, new = changed[key]
            out, n1 = re.subn(r'(<div class="post-tags">)(.*?)(</div>)',
                              lambda m: m.group(1) + remap_span_block(m.group(2)) + m.group(3), src, count=1)
            out, n2 = re.subn(r'("keywords": )(\[[^\]]*\])',
                              lambda m: m.group(1) + json.dumps(remap(json.loads(m.group(2))), ensure_ascii=False),
                              out, count=1)
            if not n1:
                stats[f'{era}: page without a post-tags block'] += 1
            if not n2:
                stats[f'{era}: page without keywords'] += 1
            if out != src:
                stats[f'{era}: post pages edited'] += 1
                if not survey:
                    path.write_text(out, encoding='utf-8')

    # ---- year pages
    for era in ERAS:
        url_to_key = {}
        for p in data[era]:
            if (era, str(p['id'])) in pages:
                url_to_key['/' + str(pages[(era, str(p['id']))].relative_to(ROOT))] = (era, str(p['id']))
        for yp in sorted((ROOT / era).glob('[12][0-9][0-9][0-9].html')):
            src = yp.read_text(encoding='utf-8')
            orig = src
            # embedded allPosts
            m = re.search(r'const allPosts = (\[.*?\]);', src)
            arr = json.loads(m.group(1))
            year_tags = set()
            for item in arr:
                if 'tags' in item:
                    item['tags'] = remap(item['tags'] or [])
                    year_tags.update(item['tags'])
            src = src[:m.start(1)] + json.dumps(arr, ensure_ascii=False) + src[m.end(1):]

            # static cards: <a class="card" href="URL"> ... <div class="card-tags">...</div>
            def card(m):
                return m.group(1) + remap_span_block(m.group(2)) + m.group(3)
            src = re.sub(r'(<a class="card" href="[^"]*">(?:(?!</a>).)*?<div class="card-tags">)(.*?)(</div>)',
                         card, src, flags=re.S)

            # filter pills: rename, drop, and remove duplicates a merge creates
            seen = set()

            def pill(m):
                n = MAP.get(m.group(1), m.group(1))
                if n is None or n in seen or n not in year_tags:
                    stats[f'{era}: filter pills removed'] += 1
                    return ''
                seen.add(n)
                if n != m.group(1):
                    stats[f'{era}: filter pills renamed'] += 1
                q = n.replace('\\', '\\\\').replace("'", "\\'")
                return f'<span class="pill" onclick="filterByTag(\'{q}\')">{html.escape(n)}</span>' + ('\n' if m.group(0).endswith('\n') else '')
            src = re.sub(r"<span class=\"pill\" onclick=\"filterByTag\('([^']*)'\)\">[^<]*</span>\n?", pill, src)
            if src != orig:
                stats[f'{era}: year pages edited'] += 1
                if not survey:
                    yp.write_text(src, encoding='utf-8')

    # ---- source files
    if not survey:
        for era, opts in ERAS.items():
            (ROOT / era / 'posts.json').write_text(json.dumps(data[era], ensure_ascii=False, **opts),
                                                   encoding='utf-8')
        ai = ROOT / 'archive' / 'index.html'
        s = ai.read_text(encoding='utf-8')
        s2 = re.sub(r'· \d+ tags', f'· {len(all_tags)} tags', s)
        if s2 != s:
            ai.write_text(s2, encoding='utf-8')
            stats['archive/index.html tag count updated'] += 1

    uses = Counter()
    for old, new in changed.values():
        for t in old:
            n = MAP.get(t, t)
            uses['dropped' if n is None else ('renamed' if n != t else 'kept')] += 1
    print(f'tags after: {len(all_tags)}')
    for k, v in sorted(stats.items()):
        print(f'  {k}: {v}')
    print(f'  tag uses on changed posts: {dict(uses)}')


if __name__ == '__main__':
    main()
