#!/usr/bin/env python3
"""Pre-step: quarantine dead-ift.tt IFTTT auto-posts from tumblr/posts.json.

- Moves every tumblr post whose content or title contains "ift.tt" into
  tumblr/posts_quarantine_ifttt.json (full objects, recoverable) ...
- EXCEPT 18 hand-verified real editorial posts (KEEP_IDS): those stay, with
  the dead ift.tt <a> links stripped (unwrap meaningful anchor text, drop
  dead-URL / empty anchors).

Idempotent: refuses to run if the quarantine file already exists.
Only touches the JSON data layer. Year-page allPosts/static-cards/counts are
adjusted later in the full Phase 1 run.
"""
import json, re, os, sys, shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'tumblr', 'posts.json')
QUAR = os.path.join(ROOT, 'tumblr', 'posts_quarantine_ifttt.json')

# 18 hand-verified real posts to KEEP (strip dead link, do not quarantine)
KEEP_IDS = {
    '139288067499','139288067844','132700998261','128640406272','115759125389',
    '108539298241','107117757640','105964312805','105969293698','103776589546',
    '95346715815','78500899580','78523366906','72823952414','72846465593',
    '72759826087','66229038473','64609008279',
}

ANCHOR_RE = re.compile(r'<a\b[^>]*ift\.tt[^>]*>(.*?)</a>', re.I | re.S)
TAG_RE = re.compile(r'<[^>]+>')

def strip_ift_links(html):
    def repl(m):
        inner = m.group(1)
        txt = TAG_RE.sub('', inner).strip()
        if 'ift.tt' in txt.lower():   # visible text is the dead URL -> drop all
            return ''
        if txt == '':                 # anchor only wrapped <br/> / nothing -> drop
            return ''
        return inner                  # meaningful label -> unwrap, keep text
    return ANCHOR_RE.sub(repl, html)

def has_ift(p):
    return 'ift.tt' in (p.get('content') or '') or 'ift.tt' in (p.get('title') or '')

def main():
    if os.path.exists(QUAR):
        sys.exit(f"REFUSING: {QUAR} already exists. Delete it to re-run.")
    posts = json.load(open(SRC, encoding='utf-8'))
    shutil.copy(SRC, SRC + '.before-ifttt-quarantine.bak')

    kept, quarantined, stripped = [], [], []
    for p in posts:
        if not has_ift(p):
            kept.append(p); continue
        if p['id'] in KEEP_IDS:
            before = p.get('content') or ''
            p['content'] = strip_ift_links(before)
            # titles of the 18 are already ift-free, but strip defensively
            if 'ift.tt' in (p.get('title') or ''):
                p['title'] = strip_ift_links(p['title'])
            residual = 'ift.tt' in (p.get('content') or '') or 'ift.tt' in (p.get('title') or '')
            stripped.append((p['id'], residual))
            kept.append(p)
        else:
            quarantined.append(p)

    json.dump(kept, open(SRC, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    json.dump(quarantined, open(QUAR, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    print(f"input posts:        {len(posts)}")
    print(f"kept in posts.json: {len(kept)}")
    print(f"quarantined:        {len(quarantined)}")
    print(f"stripped (18 keep): {len(stripped)}")
    residuals = [i for i,r in stripped if r]
    print(f"residual ift.tt after strip: {residuals if residuals else 'none'}")
    assert len(stripped) == 18, f"expected 18 keeps, got {len(stripped)}"
    assert not residuals, f"ift.tt residue in kept posts: {residuals}"

if __name__ == '__main__':
    main()
