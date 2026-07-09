#!/usr/bin/env python3
"""rewrite_year_pages.py — make year-page cards crawlable + consistent.

Per the 2026-07-07 handoff (CRITICAL discovery section), the fix must land in
BOTH places on every year page:
  1. static cards (what crawlers see): <div class="card" onclick=...> becomes
     <a class="card" href="{new static URL}">, quarantined/blocklisted posts'
     cards removed, card titles updated to the bleed-fixed titles.
  2. the embedded `const allPosts = [...]` array + the renderPost() JS template
     (what humans see after renderPosts() wipes #grid): posts filtered, titles
     fixed, a `url` field added, template rebuilt as an <a href>.

Also: adds an `a.card` CSS rule (color/text-decoration) so the div->a swap is
visually invisible; prunes filter pills whose tag no longer exists in the
year's remaining posts (filterByTag itself is untouched and keeps working —
it operates on allPosts, not the static cards).

Index pages: updates post counts on archive/index.html + tumblr/index.html
(totals + per-year pills). Homepage is NOT touched (handoff: do not touch).

Idempotent: safe to re-run (skips already-converted cards).
"""
import json, re, os, sys, html

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_posts import ROOT, load_posts, build_url_map, tags_of

def rewrite_year_page(path, era, year, posts_by_id, url_map, year_tags):
    src = open(path, encoding='utf-8').read()
    stats = {'cards_converted': 0, 'cards_removed': 0, 'titles_fixed': 0,
             'allposts_before': 0, 'allposts_after': 0, 'pills_removed': 0}

    # ---- 1. embedded allPosts array
    m = re.search(r'const allPosts = (\[.*?\]);', src)
    if not m:
        sys.exit(f"{path}: allPosts array not found")
    arr = json.loads(m.group(1))
    stats['allposts_before'] = len(arr)
    new_arr = []
    for item in arr:
        pid = str(item['id'])
        if pid not in posts_by_id:
            continue                      # quarantined / blocklisted
        p = posts_by_id[pid]
        item['title'] = p.get('title') or ''
        item['url'] = url_map[pid]
        new_arr.append(item)
    stats['allposts_after'] = len(new_arr)
    src = src[:m.start(1)] + json.dumps(new_arr, ensure_ascii=False) + src[m.end(1):]

    # ---- 2. renderPost template: div card -> a card
    open_old = f"""<div class="card" onclick="location.href='/{era}/post.html?id=${{post.id}}'">"""
    open_new = '<a class="card" href="${post.url}">'
    if open_old in src:
        src = src.replace(open_old, open_new)
        close_old = "\n            </div>\n        `;"
        close_new = "\n            </a>\n        `;"
        if src.count(close_old) != 1:
            sys.exit(f"{path}: renderPost closing tag pattern matched {src.count(close_old)} times (expected 1)")
        src = src.replace(close_old, close_new)

    # ---- 3. static cards
    CARD_OPEN = re.compile(
        rf'<div class="card" onclick="location\.href=\'/{era}/post\.html\?id=([^\']+)\'">')
    TOKEN = re.compile(r'<div\b|</div>')
    out = []
    pos = 0
    while True:
        mo = CARD_OPEN.search(src, pos)
        if not mo:
            out.append(src[pos:])
            break
        out.append(src[pos:mo.start()])
        pid = str(mo.group(1))
        # find matching close via div-depth from the card's opening tag
        depth = 1
        i = mo.end()
        while depth > 0:
            t = TOKEN.search(src, i)
            if not t:
                sys.exit(f"{path}: unbalanced card block for id={pid}")
            depth += 1 if t.group(0) == '<div' else -1
            i = t.end()
        block = src[mo.start():i]           # full card incl. closing </div>
        pos = i
        if pid not in posts_by_id:
            stats['cards_removed'] += 1
            continue                        # drop the card entirely
        inner = block[len(mo.group(0)):-len('</div>')]
        # title fix inside the card
        p = posts_by_id[pid]
        tm = re.search(r'(<h3 class="card-title">)(.*?)(</h3>)', inner, re.S)
        if tm:
            want = html.escape(p.get('title') or '')
            if tm.group(2) != want:
                inner = inner[:tm.start(2)] + want + inner[tm.end(2):]
                stats['titles_fixed'] += 1
        out.append(f'<a class="card" href="{url_map[pid]}">' + inner + '</a>')
        stats['cards_converted'] += 1
    src = ''.join(out)

    # ---- 4. a.card CSS (visual parity for the div->a swap)
    if 'a.card {' not in src:
        anchor = '.card:hover {'
        rule = "a.card {\n        color: inherit;\n        text-decoration: none;\n    }\n\n    \n    "
        if anchor not in src:
            sys.exit(f"{path}: .card:hover CSS anchor not found")
        src = src.replace(anchor, rule + anchor, 1)

    # ---- 5. prune filter pills for tags that no longer exist this year
    def pill_sub(m):
        tag = m.group(1)
        if tag in year_tags:
            return m.group(0)
        stats['pills_removed'] += 1
        return ''
    src = re.sub(r"<span class=\"pill\" onclick=\"filterByTag\('([^']*)'\)\">[^<]*</span>\n?",
                 pill_sub, src)

    open(path, 'w', encoding='utf-8').write(src)
    return stats

def update_counts(wp, tb):
    tb_total = len(tb)
    grand = len(wp) + len(tb)
    tb_years = {}
    for p in tb:
        tb_years[str(p['year'])] = tb_years.get(str(p['year']), 0) + 1
    all_tags = set()
    for p in wp + tb:
        all_tags.update(tags_of(p))

    def fix_year_pills(src, era, counts):
        def sub(m):
            y = m.group(1)
            return m.group(0).replace(m.group(2), f'({counts.get(y, 0)})')
        return re.sub(
            rf'<a href="/{era}/(\d{{4}})\.html" class="year-link">\d{{4}} <span class="count">(\(\d+\))</span></a>',
            sub, src)

    # archive/index.html — grand total, tag count, tumblr era count + pills
    ap = os.path.join(ROOT, 'archive', 'index.html')
    s = open(ap, encoding='utf-8').read()
    s = re.sub(r'4,769 posts', f'{grand:,} posts', s)
    s = re.sub(r'· \d+ tags', f'· {len(all_tags)} tags', s)
    s = re.sub(r'4,123 posts', f'{tb_total:,} posts', s)
    s = fix_year_pills(s, 'tumblr', tb_years)
    open(ap, 'w', encoding='utf-8').write(s)

    # tumblr/index.html — era totals + per-year pills
    tp = os.path.join(ROOT, 'tumblr', 'index.html')
    s = open(tp, encoding='utf-8').read()
    s = re.sub(r'4,123 posts', f'{tb_total:,} posts', s)
    s = fix_year_pills(s, 'tumblr', tb_years)
    open(tp, 'w', encoding='utf-8').write(s)
    print(f"counts updated: grand={grand:,} tumblr={tb_total:,} tags={len(all_tags)}")

def main():
    wp, tb, _ = load_posts()
    url_map, _ = build_url_map(wp, tb)
    posts_by_id = {str(p['id']): p for p in wp + tb}

    jobs = [(os.path.join(ROOT, 'archive', f'{y}.html'), 'archive', y) for y in range(2005, 2009)]
    jobs += [(os.path.join(ROOT, 'tumblr', f'{y}.html'), 'tumblr', y) for y in range(2007, 2022)]

    year_tag_map = {}
    for era, posts in (('archive', wp), ('tumblr', tb)):
        for p in posts:
            year_tag_map.setdefault((era, str(p['year'])), set()).update(tags_of(p))

    total = {'cards_converted': 0, 'cards_removed': 0, 'titles_fixed': 0, 'pills_removed': 0}
    for path, era, year in jobs:
        st = rewrite_year_page(path, era, str(year), posts_by_id, url_map,
                               year_tag_map.get((era, str(year)), set()))
        for k in total:
            total[k] += st[k]
        print(f"{era}/{year}: cards {st['cards_converted']} converted, {st['cards_removed']} removed, "
              f"{st['titles_fixed']} titles fixed | allPosts {st['allposts_before']}->{st['allposts_after']} "
              f"| pills -{st['pills_removed']}")
    print("TOTAL:", total)

    update_counts(wp, tb)

if __name__ == '__main__':
    main()
