#!/usr/bin/env python3
"""build_posts.py — generate static, crawler-visible post pages for undomondo.

Reads archive/posts.json (WP era, 646) + tumblr/posts.json (Tumblr era) and
writes one static HTML page per post:
    WP:     /archive/{year}/{slug}.html
    Tumblr: /tumblr/{year}/{slug}.html

Python 3 stdlib only. Idempotent (deletes + regenerates output year dirs).
    --pilot   generate only the curated PILOT_IDS sample (~20 posts), but still
              build the FULL URL map + collision guard over every post.

Phase 1 full mode also emits:
    archive/urlmap.json + tumblr/urlmap.json   (id -> new path, for redirectors)
    sitemap.xml (index) + sitemap-core/archive/tumblr.xml, robots.txt, llms.txt

Data-layer steps run first:
    - blocklist quarantine: ids in scripts/blocklist.json are moved (full
      objects, recoverable) from tumblr/posts.json to tumblr/posts_blocklist.json
    - title-bleed fix (in-memory, conservative): tumblr titles fused with the
      first content line are truncated to the real first block. Slugs, <title>,
      og:title, JSON-LD headline all use the FIXED title. Year-page rewriter
      imports fixed_title() so card titles + allPosts stay consistent.

Design/plumbing is a faithful port of archive/post.html & tumblr/post.html:
same CSS (extracted verbatim to /assets/post.css), same buildEmbeds() media
logic, same footer/site-nav, plus a top black year-nav band, the bottom
.post-nav, and the approved newsletter CTA band. Invents no design.
"""
import json, re, os, sys, html, unicodedata, shutil
from datetime import datetime
from urllib.parse import quote

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARCHIVE_JSON = os.path.join(ROOT, 'archive', 'posts.json')
TUMBLR_JSON  = os.path.join(ROOT, 'tumblr', 'posts.json')
BLOCKLIST    = os.path.join(ROOT, 'scripts', 'blocklist.json')
BLOCK_OUT    = os.path.join(ROOT, 'tumblr', 'posts_blocklist.json')
POST_HTML    = os.path.join(ROOT, 'scripts', 'post_template.html')  # CSS + footer source (pre-redirector copy of archive/post.html)
YEAR_HTML    = os.path.join(ROOT, 'tumblr', '2021.html')    # year-nav CSS source
CSS_OUT      = os.path.join(ROOT, 'assets', 'post.css')

CANON = 'https://www.undomondo.com'   # apex 301s to www (late correction)

FONTS_LINK = ('<link rel="preconnect" href="https://fonts.googleapis.com">\n'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
    '<link href="https://fonts.googleapis.com/css2?family=Fugaz+One&family=Dela+Gothic+One&family=Fugaz+One&family=Space+Mono:wght@400;700&family=DM+Sans:wght@400;500;700&family=Merriweather:ital,wght@0,400;0,700;1,400&display=swap" rel="stylesheet">')

# Curated pilot sample — mix of every case the reviewer must eyeball.
PILOT_IDS = {
    '4', '709', '10', '20', '144', '599', '146', '143',
    '642897410056749056', '640655904559251456', '638965639848017920',
    '188582453704', '181458182619', '74722566664', '166551986107',
    '149004741835', '132700998261', '38788456398', '621360948792410112',
}

# ---------------------------------------------------------------- helpers

def parse_dt(s):
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    return datetime.min

def iso_date(s):
    return s.replace(' ', 'T') if ' ' in s else s

def fmt_human(dt):
    return f"{dt.strftime('%B')} {dt.day}, {dt.year}"

def month_year(dt):
    return f"{dt.strftime('%B')} {dt.year}"

def slugify(s):
    s = unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode()
    s = re.sub(r'[^a-zA-Z0-9]+', '-', s).strip('-').lower()
    return s[:60].strip('-')

def tags_of(post):
    t = post.get('tags')
    if isinstance(t, list):
        return [str(x) for x in t]
    if isinstance(t, str):
        try:
            import ast
            v = ast.literal_eval(t)
            return [str(x) for x in v] if isinstance(v, list) else []
        except Exception:
            return []
    return []

_TAG_STRIP = re.compile(r'<[^>]+>')
_WS = re.compile(r'\s+')
def strip_html(s):
    s = _TAG_STRIP.sub(' ', s or '')
    s = html.unescape(s)
    return _WS.sub(' ', s).strip()

def enc_uri_component(s):
    return quote(s, safe="-_.!~*'()")

# ---------------------------------------------------------------- title-bleed fix
# Tumblr scrape fused title + first content line(s) with no separator, then
# truncated at ~100 chars ("Ishmael - Mercy, Mercy MeGood gospel house on...").
# Conservative repair: title is truncated to the first content block ONLY when
# the fused tail provably continues into the following content blocks.

_RECOVERED = re.compile(r'<a\b[^>]*tumblr-recovered-embed[^>]*>.*?</a>', re.I | re.S)
_BLOCK_SPLIT = re.compile(r'</p>|</h[1-6]>|</blockquote>|</div>|</li>|<br\s*/?>', re.I)
_URLTOK = re.compile(r'^(?:https?://\S+\s*)+')
_USERATTR = re.compile(r'^[A-Za-z0-9_-]+:$')

def _content_blocks(content):
    c = _RECOVERED.sub('', content or '')
    out = []
    for chunk in _BLOCK_SPLIT.split(c):
        t = _WS.sub(' ', html.unescape(_TAG_STRIP.sub('', chunk))).strip()
        t = _URLTOK.sub('', t).strip()
        if t:
            out.append(t)
    return out

def _nospace(s):
    return re.sub(r'\s+', '', s)

def fixed_title(post):
    """Return (title, was_fixed). Conservative: on any ambiguity, keep as-is."""
    title = (post.get('title') or '').strip()
    if not title:
        return title, False
    bl = _content_blocks(post.get('content') or '')
    if not bl:
        return title, False
    b0 = bl[0]
    if _USERATTR.match(b0):          # reblog attribution ("user:") — ambiguous
        return title, False
    if len(b0) < 8:                  # too short to be a trustworthy title
        return title, False
    t = _nospace(title)
    b = _nospace(b0)
    if not b or not t.startswith(b):
        return title, False
    tail = t[len(b):]
    if len(tail) < 4:                # no meaningful bleed
        return title, False
    rest = _nospace(''.join(bl[1:]))
    if rest.startswith(tail):        # tail provably continues into content
        return b0, True
    return title, False

# ---------------------------------------------------------------- data loading

def apply_blocklist(tb):
    """Move blocklisted posts (full objects) out of tumblr/posts.json into
    tumblr/posts_blocklist.json. Recoverable + idempotent."""
    if not os.path.exists(BLOCKLIST):
        return tb, 0
    block_ids = {str(x) for x in json.load(open(BLOCKLIST, encoding='utf-8'))}
    hit = [p for p in tb if str(p['id']) in block_ids]
    if not hit:
        return tb, 0
    keep = [p for p in tb if str(p['id']) not in block_ids]
    existing = []
    if os.path.exists(BLOCK_OUT):
        existing = json.load(open(BLOCK_OUT, encoding='utf-8'))
        have = {str(p['id']) for p in existing}
        hit = [p for p in hit if str(p['id']) not in have]
    json.dump(existing + hit, open(BLOCK_OUT, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    json.dump(keep, open(TUMBLR_JSON, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    return keep, len(hit)

def load_posts(verbose=False):
    """Load both eras with blocklist applied and tumblr titles bleed-fixed.
    THE single entry point — year-page rewriter imports this too."""
    wp = json.load(open(ARCHIVE_JSON, encoding='utf-8'))
    tb = json.load(open(TUMBLR_JSON, encoding='utf-8'))
    tb, moved = apply_blocklist(tb)
    fixes = []
    for p in tb:
        new, changed = fixed_title(p)
        if changed:
            fixes.append((str(p['id']), p['title'], new))
            p['title'] = new
    if verbose:
        print(f"blocklist: moved {moved} post(s) to {os.path.basename(BLOCK_OUT)}")
        print(f"title-bleed fixes applied: {len(fixes)}")
    return wp, tb, fixes

# ---------------------------------------------------------------- buildEmbeds
# Faithful port of buildEmbeds() from archive/post.html.

_YT = re.compile(r"(?:youtube\.com/watch\?[^\"'<>\s]*?v=|youtu\.be/|youtube\.com/embed/|youtube\.com/v/)([A-Za-z0-9_-]{11})", re.I)
_VIMEO = re.compile(r"vimeo\.com/(?:video/)?(\d+)", re.I)
_MOOGA = re.compile(r"moogaloop\.swf\?clip_id=(\d+)", re.I)
_SC = re.compile(r"https?://(?:www\.|m\.)?soundcloud\.com/[A-Za-z0-9][^\s\"<>?#]*", re.I)
_MC = re.compile(r"https?://(?:www\.)?mixcloud\.com/([^\s\"<>?#]+?/[^\s\"<>?#]+?/)", re.I)
_OBJ = re.compile(r"<object\b[^>]*>[\s\S]*?</object>", re.I)
_EMB = re.compile(r"<embed\b[^>]*/?>", re.I)

def build_embeds(content_html):
    if not content_html:
        return ''
    seen = set()
    embeds = []

    for m in _YT.finditer(content_html):
        key = 'yt:' + m.group(1)
        if key not in seen:
            seen.add(key)
            embeds.append(f'<div class="embed-wrap"><iframe src="https://www.youtube-nocookie.com/embed/{m.group(1)}" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen loading="lazy"></iframe></div>')

    for rx in (_VIMEO, _MOOGA):
        for m in rx.finditer(content_html):
            key = 'vimeo:' + m.group(1)
            if key not in seen:
                seen.add(key)
                embeds.append(f'<div class="embed-wrap"><iframe src="https://player.vimeo.com/video/{m.group(1)}" allow="autoplay; fullscreen; picture-in-picture" allowfullscreen loading="lazy"></iframe></div>')

    for m in _SC.finditer(content_html):
        clean = re.sub(r'[.,;:!?)]+$', '', m.group(0))
        key = 'sc:' + clean
        if key not in seen:
            seen.add(key)
            src = ('https://w.soundcloud.com/player/?url=' + enc_uri_component(clean)
                   + '&color=%23D62828&auto_play=false&hide_related=true&show_comments=false&show_user=true&show_reposts=false&show_teaser=false')
            embeds.append(f'<div class="embed-wrap embed-sc"><iframe src="{src}" scrolling="no" loading="lazy"></iframe></div>')

    for m in _MC.finditer(content_html):
        feed = '/' + m.group(1).lstrip('/')
        key = 'mc:' + feed
        if key not in seen:
            seen.add(key)
            src = 'https://www.mixcloud.com/widget/iframe/?feed=' + enc_uri_component(feed) + '&hide_cover=1&light=1'
            embeds.append(f'<div class="embed-wrap embed-mc"><iframe src="{src}" allow="autoplay" loading="lazy"></iframe></div>')

    cleaned = _EMB.sub('', _OBJ.sub('', content_html))
    return ''.join(embeds) + cleaned

# ---------------------------------------------------------------- CSS extraction

NEWSLETTER_CSS = """
    /* newsletter CTA band (approved 2026-07-09) */
    .newsletter-cta {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 1rem;
        flex-wrap: wrap;
        margin-top: 3rem;
        padding: 1.25rem 1.5rem;
        border: 2px solid #111;
    }
    .newsletter-cta .cta-line {
        font-family: 'Space Mono', monospace;
        font-size: 0.85rem;
        color: #111;
    }
    .newsletter-cta .cta-link {
        border: 2px solid #D62828;
        padding: 8px 16px;
        font-family: 'DM Sans', sans-serif;
        font-size: 12px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 2px;
        text-decoration: none;
        color: #D62828;
        white-space: nowrap;
        transition: background 0.15s, color 0.15s;
    }
    .newsletter-cta .cta-link:hover {
        background: #D62828;
        color: #F2EFE5;
    }
"""

def write_css():
    src = open(POST_HTML, encoding='utf-8').read()
    m = re.search(r'<style>(.*?)</style>', src, re.S)
    if not m:
        sys.exit("could not extract <style> from post.html")
    css = m.group(1).strip('\n')
    year = open(YEAR_HTML, encoding='utf-8').read()
    parts = []
    for sel in ('.year-nav', '.year-nav a, .year-nav span', '.year-nav a:hover', '.year-nav .current'):
        mm = re.search(re.escape(sel) + r'\s*\{[^}]*\}', year)
        if mm:
            parts.append(mm.group(0))
    ynav = '\n\n'.join(parts)
    out = (css
           + "\n\n    /* year-nav band (extracted from year pages) */\n    "
           + ynav.replace('\n', '\n    ')
           + "\n" + NEWSLETTER_CSS)
    os.makedirs(os.path.dirname(CSS_OUT), exist_ok=True)
    open(CSS_OUT, 'w', encoding='utf-8').write(out)

# ---------------------------------------------------------------- URL map + guard

def build_url_map(wp, tb):
    url_map = {}
    used = {}
    base_resolved = 0
    unresolved = []

    def place(era, post):
        nonlocal base_resolved
        year = str(post['year'])
        pid = str(post['id'])
        if era == 'archive':
            slug = post['slug']
        else:
            slug = slugify(post.get('title') or '')
            if not slug:
                slug = f'post-{pid}'
        path = f'/{era}/{year}/{slug}.html'
        if path in used and used[path] != pid:
            path = f'/{era}/{year}/{slug}-{pid[-6:]}.html'
            base_resolved += 1
            if path in used and used[path] != pid:
                unresolved.append((pid, path))
        used[path] = pid
        url_map[pid] = path

    for p in wp:
        place('archive', p)
    for p in tb:
        place('tumblr', p)

    if unresolved:
        for pid, path in unresolved:
            print(f"  UNRESOLVED COLLISION id={pid} path={path}", file=sys.stderr)
        sys.exit(f"HARD FAIL: {len(unresolved)} unresolved URL collision(s)")
    return url_map, base_resolved

# ---------------------------------------------------------------- page render

SITE_NAV = '''<header class="site-nav">
    <div class="site-nav-inner">
        <a href="/" class="wordmark"><span style="font-family:'Dela Gothic One',sans-serif; font-size:16px; color:#111111; text-transform:uppercase; letter-spacing:0.02em; line-height:1;">UNDOMONDO</span></a>
        <nav class="nav-links">
            <a href="/">Home</a>
            <a href="{hub}" class="current">{hublabel}</a>
            <a href="https://undomondo.substack.com" target="_blank" rel="noopener">Newsletter</a>
        </nav>
    </div>
</header>'''

NEWSLETTER_CTA = '''<div class="newsletter-cta">
            <span class="cta-line">I've been digging like this since 2005.</span>
            <a class="cta-link" href="https://undomondo.substack.com" target="_blank" rel="noopener">&rarr; Mondo Times, the newsletter</a>
        </div>'''

FOOTER = open(POST_HTML, encoding='utf-8').read()
FOOTER = re.search(r'(<footer[\s\S]*?</footer>)', FOOTER).group(1)

def render_page(post, era, url_map, top_prev, top_next, bot_prev, bot_next):
    pid = str(post['id'])
    year = str(post['year'])
    dt = parse_dt(post['date'])
    raw_title = (post.get('title') or '').strip()
    title = raw_title if raw_title else 'Untitled'
    path = url_map[pid]
    canonical = CANON + path

    if raw_title:
        title_tag = f'{raw_title} · undomondo'
        og_title = raw_title
    else:
        title_tag = f'undomondo archive · {month_year(dt)}'
        og_title = f'undomondo archive · {month_year(dt)}'
    body_text = strip_html(post.get('content') or '')
    if body_text:
        desc = body_text[:155].rstrip()
    else:
        desc = f'From the undomondo archive, {month_year(dt)}.'

    tags = tags_of(post)
    ld = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": title,
        "datePublished": iso_date(post['date']),
        "keywords": tags,
        "author": {"@type": "Organization", "name": "undomondo"},
        "url": canonical,
    }
    ld_json = json.dumps(ld, ensure_ascii=False)

    e = html.escape
    head = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{e(title_tag)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{e(canonical)}">
<meta property="og:type" content="article">
<meta property="og:title" content="{e(og_title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{e(canonical)}">
{FONTS_LINK}
<link rel="stylesheet" href="/assets/post.css">
<script type="application/ld+json">{ld_json}</script>
</head>'''

    hub = f'/{era}/'
    hublabel = 'Archive' if era == 'archive' else 'Tumblr'
    site_nav = SITE_NAV.format(hub=hub, hublabel=hublabel)

    def cell(link, label):
        if link:
            return f'<a href="{e(link)}">{e(label)}</a>'
        return f'<span>{e(label)}</span>'
    top = ['<nav class="year-nav">',
           f'<a href="/{era}/{year}.html">← {year}</a>',
           ' · ',
           cell(top_prev[0] if top_prev else None, '← prev post' if top_prev else '← prev'),
           ' · ',
           cell(top_next[0] if top_next else None, 'next post →' if top_next else 'next'),
           '</nav>']
    top_band = ''.join(top)

    nav = ['<div class="post-nav"><div style="flex:1;">']
    if bot_prev:
        nav.append(f'<a href="{e(bot_prev[0])}">← Previous</a>')
    nav.append('</div><div class="nav-center">')
    nav.append(f'<a href="/{era}/{year}.html">← Back to {year}</a>')
    nav.append('</div><div style="flex:1; text-align: right;">')
    if bot_next:
        nav.append(f'<a href="{e(bot_next[0])}">Next →</a>')
    nav.append('</div></div>')
    bottom_nav = ''.join(nav)

    tags_html = ''
    if tags:
        pills = ''.join(f'<span class="tag">{e(t)}</span>' for t in tags)
        tags_html = f'<div class="post-tags">{pills}</div>'

    content_html = build_embeds(post.get('content') or '')
    # exactly one <h1> per page: demote any h1 inside post content to h2
    content_html = re.sub(r'<(/?)h1\b', r'<\1h2', content_html, flags=re.I)

    body = f'''<body>
{site_nav}
<div class="container">
    <article>
        {top_band}
        <div class="post-header">
            <div class="post-meta"><time datetime="{e(iso_date(post['date']))}">{e(fmt_human(dt))}</time> · {year}</div>
            <h1 class="post-title">{e(title)}</h1>
        </div>
        <div class="post-content">{content_html}</div>
        {tags_html}
        {bottom_nav}
        {NEWSLETTER_CTA}
    </article>
</div>
{FOOTER}
</body>
</html>'''
    return head + '\n' + body

# ---------------------------------------------------------------- sitemaps etc.

def write_sitemaps(wp, tb, url_map):
    def urlset(entries):
        rows = []
        for loc, lastmod in entries:
            lm = f'<lastmod>{lastmod}</lastmod>' if lastmod else ''
            rows.append(f'<url><loc>{html.escape(loc)}</loc>{lm}</url>')
        return ('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                + '\n'.join(rows) + '\n</urlset>\n')

    core = [(f'{CANON}/', None), (f'{CANON}/archive/', None), (f'{CANON}/tumblr/', None)]
    for y in range(2005, 2009):
        core.append((f'{CANON}/archive/{y}.html', None))
    for y in range(2007, 2022):
        core.append((f'{CANON}/tumblr/{y}.html', None))
    open(os.path.join(ROOT, 'sitemap-core.xml'), 'w', encoding='utf-8').write(urlset(core))

    def post_entries(posts):
        out = []
        for p in sorted(posts, key=lambda p: parse_dt(p['date'])):
            out.append((CANON + url_map[str(p['id'])], str(p['date']).split(' ')[0]))
        return out
    open(os.path.join(ROOT, 'sitemap-archive.xml'), 'w', encoding='utf-8').write(urlset(post_entries(wp)))
    open(os.path.join(ROOT, 'sitemap-tumblr.xml'), 'w', encoding='utf-8').write(urlset(post_entries(tb)))

    idx = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
           + '\n'.join(f'<sitemap><loc>{CANON}/{n}</loc></sitemap>'
                       for n in ('sitemap-core.xml', 'sitemap-archive.xml', 'sitemap-tumblr.xml'))
           + '\n</sitemapindex>\n')
    open(os.path.join(ROOT, 'sitemap.xml'), 'w', encoding='utf-8').write(idx)

ROBOTS = f"""User-agent: *
Allow: /

User-agent: GPTBot
Allow: /

User-agent: ClaudeBot
Allow: /

User-agent: Claude-Web
Allow: /

User-agent: PerplexityBot
Allow: /

User-agent: Google-Extended
Allow: /

Sitemap: {CANON}/sitemap.xml
"""

def llms_txt(wp_n, tb_n):
    return f"""# undomondo

> Music blog, radioshow and DJ outlet, running since 2005. Istanbul / Barcelona / Internet.
> Written and curated by one person: deep cuts, reissues, radio shows, mixes, obituaries,
> and two decades of digging across jazz, global grooves, electronic, folk and everything between.

## The archive ({wp_n + tb_n} posts, 2005-2021)

Two eras, both fully static and crawlable:

- WordPress era (2005-2008, {wp_n} posts): {CANON}/archive/
  Post URLs: {CANON}/archive/{{year}}/{{slug}}.html
- Tumblr era (2007-2021, {tb_n} posts): {CANON}/tumblr/
  Post URLs: {CANON}/tumblr/{{year}}/{{slug}}.html

Year hubs: /archive/2005.html ... /archive/2008.html and /tumblr/2007.html ... /tumblr/2021.html

## Machine-readable

- Sitemap index: {CANON}/sitemap.xml
- Every post page carries schema.org BlogPosting JSON-LD.

## Current output

- Newsletter (Mondo Times): https://undomondo.substack.com
- Homepage: {CANON}/
"""

def write_urlmaps(wp, tb, url_map):
    for era, posts in (('archive', wp), ('tumblr', tb)):
        m = {str(p['id']): url_map[str(p['id'])] for p in posts}
        json.dump(m, open(os.path.join(ROOT, era, 'urlmap.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, separators=(',', ':'))

# ---------------------------------------------------------------- main

def neighbors_map(posts, url_map, ascending):
    ordered = sorted(range(len(posts)),
                     key=lambda i: (parse_dt(posts[i]['date']), i),
                     reverse=not ascending)
    out = {}
    for rank, idx in enumerate(ordered):
        pid = str(posts[idx]['id'])
        prev = ordered[rank-1] if rank > 0 else None
        nxt = ordered[rank+1] if rank < len(ordered)-1 else None
        prev_link = (url_map[str(posts[prev]['id'])],) if prev is not None else None
        next_link = (url_map[str(posts[nxt]['id'])],) if nxt is not None else None
        out[pid] = (prev_link, next_link)
    return out

def clean_output_dirs():
    for era in ('archive', 'tumblr'):
        base = os.path.join(ROOT, era)
        for name in os.listdir(base):
            p = os.path.join(base, name)
            if os.path.isdir(p) and re.fullmatch(r'20\d\d', name):
                shutil.rmtree(p)

def main():
    pilot = '--pilot' in sys.argv
    wp, tb, fixes = load_posts(verbose=True)

    write_css()
    url_map, base_resolved = build_url_map(wp, tb)
    print(f"URL map: {len(url_map)} paths | collision-suffix resolutions: {base_resolved} | unresolved: 0")

    clean_output_dirs()
    written = 0
    for era, posts in (('archive', wp), ('tumblr', tb)):
        top_nb = neighbors_map(posts, url_map, ascending=True)
        bot_nb = {}
        by_year = {}
        for p in posts:
            by_year.setdefault(str(p['year']), []).append(p)
        for yr, yps in by_year.items():
            bot_nb.update(neighbors_map(yps, url_map, ascending=False))

        for p in posts:
            pid = str(p['id'])
            if pilot and pid not in PILOT_IDS:
                continue
            path = url_map[pid]
            out_path = os.path.join(ROOT, path.lstrip('/'))
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            tp, tn = top_nb[pid]
            bp, bn = bot_nb[pid]
            page = render_page(p, era, url_map, tp, tn, bp, bn)
            open(out_path, 'w', encoding='utf-8').write(page)
            written += 1

    write_urlmaps(wp, tb, url_map)
    if not pilot:
        write_sitemaps(wp, tb, url_map)
        open(os.path.join(ROOT, 'robots.txt'), 'w', encoding='utf-8').write(ROBOTS)
        open(os.path.join(ROOT, 'llms.txt'), 'w', encoding='utf-8').write(llms_txt(len(wp), len(tb)))
        print("wrote urlmaps, sitemap.xml (+3), robots.txt, llms.txt")

    print(f"pages written: {written}{' (PILOT)' if pilot else ''} | wp={len(wp)} tb={len(tb)}")

if __name__ == '__main__':
    main()
