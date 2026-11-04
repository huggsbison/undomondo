"""Dead-link report for the old posts. Report only: no post is changed.

Step 1 (no network needed):
  python3 scripts/dead_links.py list
    Pulls every external link and embed out of archive/posts.json and
    tumblr/posts.json and writes docs/dead_links.csv. Links on his own R2
    bucket (pub-...r2.dev) are skipped. It fills in what is already known
    without going online:
      - YouTube and Vimeo results from the 2026-07-11 check stored in
        scripts/tumblr_embed_liveness.json
      - hosts that are known to have shut down (see SHUT_DOWN below)
    Everything else is marked "not checked".

Step 2 (needs open network; was blocked in the cloud session):
  python3 scripts/dead_links.py check [--limit N]
    Checks the "not checked" rows politely: a HEAD request (falling back to
    a 1-byte GET when a server refuses HEAD), one request at a time per host,
    at least 2 seconds apart per host, up to 8 hosts in parallel. Updates the
    CSV in place, so it can be stopped and re-run.

  python3 scripts/dead_links.py counts
    Prints counts by type, status and host (what goes in the PR).
"""
import csv
import html
import json
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSV = ROOT / 'docs' / 'dead_links.csv'
CACHE = ROOT / 'scripts' / 'tumblr_embed_liveness.json'
CACHE_DATE = '2026-07-11'
UA = 'undomondo-linkcheck/1.0 (+https://www.undomondo.com)'
FIELDS = ['era', 'post', 'link', 'link_type', 'host', 'status', 'status_source', 'suggested_action', 'note']

# Hosts that are gone as a whole. General web history, not checked from here.
SHUT_DOWN = {
    'mp3download.myspace.com': 'MySpace lost its pre-2015 music uploads (2019)',
    'vids.myspace.com': 'old MySpace video player, retired',
    'lads.myspace.com': 'old MySpace player, retired',
    'mediaservices.myspace.com': 'old MySpace player, retired',
    'www.fileden.com': 'FileDen file host, closed',
    'fileden.com': 'FileDen file host, closed',
    'mog.com': 'MOG streaming, closed 2014',
    'www.mog.com': 'MOG streaming, closed 2014',
    'imeem.com': 'imeem, closed 2009',
    'www.imeem.com': 'imeem, closed 2009',
    'del.icio.us': 'del.icio.us, closed',
    'www.muxtape.com': 'Muxtape, closed',
    'muxtape.com': 'Muxtape, closed',
    'www.odeo.com': 'Odeo, closed',
    'odeo.com': 'Odeo, closed',
    'www.divshare.com': 'DivShare, closed',
    'www.zshare.net': 'zShare, closed',
    'www.megaupload.com': 'Megaupload, seized 2012',
    'rapidshare.com': 'RapidShare, closed 2015',
    'www.esnips.com': 'eSnips, closed',
    'www.geocities.com': 'GeoCities, closed 2009',
    'geocities.com': 'GeoCities, closed 2009',
}

MEDIA_EXT = re.compile(r'\.(mp3|m4a|ogg|wav|aac|flac|wma)(\?|$)', re.I)
IMG_EXT = re.compile(r'\.(jpe?g|png|gif|webp|bmp)(\?|$)', re.I)
ATTR = re.compile(r'<(\w+)\b[^>]*?\b(href|src|data|value)\s*=\s*["\']([^"\']+)["\']', re.I)
YT_ID = re.compile(r'(?:youtube(?:-nocookie)?\.com/(?:embed/|v/|watch\?(?:.*&)?v=)|youtu\.be/)([\w-]{11})')
VIMEO_ID = re.compile(r'vimeo\.com/(?:video/|moogaloop\.swf\?clip_id=)?(\d+)')


def link_type(tag, url, host):
    h = host or ''
    if 'youtube' in h or 'youtu.be' in h:
        return 'YouTube'
    if 'soundcloud' in h or h == 'snd.sc':
        return 'SoundCloud'
    if MEDIA_EXT.search(urllib.parse.urlsplit(url).path):
        return 'mp3'
    if tag == 'img' or IMG_EXT.search(urllib.parse.urlsplit(url).path) or 'staticflickr' in h:
        return 'image'
    if tag in ('iframe', 'embed', 'object', 'param', 'audio', 'video', 'source') or 'vimeo' in h:
        return 'other'      # players and embeds other than YouTube/SoundCloud
    return 'article'


def action(kind, ok):
    if ok:
        return 'keep'
    return 'replace with Wayback link' if kind == 'article' else 'remove'


def build_list():
    cache = json.loads(CACHE.read_text(encoding='utf-8'))['status']
    rows, skipped = [], 0
    for era in ('archive', 'tumblr'):
        posts = json.loads((ROOT / era / 'posts.json').read_text(encoding='utf-8'))
        urlmap = json.loads((ROOT / era / 'urlmap.json').read_text(encoding='utf-8'))
        for p in posts:
            path = urlmap.get(str(p['id'])) or (f"/archive/{p['year']}/{p['slug']}.html" if era == 'archive' else f"tumblr id {p['id']}")
            seen = set()
            for m in ATTR.finditer(p.get('content') or ''):
                tag, url = m.group(1).lower(), html.unescape(m.group(3)).strip()
                if not re.match(r'https?://', url, re.I) or url in seen:
                    continue
                seen.add(url)
                host = (urllib.parse.urlsplit(url).hostname or '').lower()
                if host.endswith('.r2.dev'):
                    skipped += 1
                    continue
                kind = link_type(tag, url, host)
                row = dict(era='wordpress' if era == 'archive' else 'tumblr', post=path, link=url,
                           link_type=kind, host=host, status='not checked', status_source='',
                           suggested_action='pending check', note='')
                yt, vm = YT_ID.search(url), VIMEO_ID.search(url)
                code = None
                if kind == 'YouTube' and yt and yt.group(1) in cache['youtube']:
                    code, src = cache['youtube'][yt.group(1)], f'YouTube oEmbed check {CACHE_DATE}'
                elif vm and vm.group(1) in cache['vimeo']:
                    code, src = cache['vimeo'][vm.group(1)], f'Vimeo oEmbed check {CACHE_DATE}'
                if code is not None:
                    row.update(status=str(code), status_source=src)
                    if code == 200:
                        row['suggested_action'] = 'keep'
                    elif code == 401:
                        row.update(suggested_action='keep',
                                   note='video exists but its owner blocks embedding; link out instead of embedding')
                    else:
                        row.update(suggested_action='remove', note='video deleted or private')
                elif host in SHUT_DOWN:
                    row.update(status='host shut down', status_source='known host closure, not requested',
                               suggested_action=action(kind, False), note=SHUT_DOWN[host])
                rows.append(row)
    CSV.parent.mkdir(exist_ok=True)
    write(rows)
    print(f'{len(rows)} links written, {skipped} R2 links skipped')


def write(rows):
    with open(CSV, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


def probe(url):
    """Return (status, final_url). Status is an HTTP code or a short error."""
    # Old posts have raw spaces and other unsafe characters in some links;
    # percent-encode them so they get checked instead of failing locally.
    url = urllib.parse.quote(url, safe=":/?#[]@!$&'()*+,;=%~")
    for method, extra in (('HEAD', {}), ('GET', {'Range': 'bytes=0-0'})):
        req = urllib.request.Request(url, method=method, headers={'User-Agent': UA, **extra})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return str(r.status), r.geturl()
        except urllib.error.HTTPError as e:
            if method == 'HEAD' and e.code in (403, 405, 501):
                continue          # some servers refuse HEAD; try a tiny GET
            return str(e.code), url
        except Exception as e:
            reason = getattr(e, 'reason', e)
            return f'error: {str(reason)[:60]}', url
    return 'error', url


def check(limit=None):
    rows = list(csv.DictReader(open(CSV, encoding='utf-8')))
    todo = [r for r in rows if r['status'] == 'not checked'][:limit]
    by_host = defaultdict(list)
    for r in todo:
        by_host[r['host']].append(r)
    lock, done = threading.Lock(), [0]

    def run_host(items):
        cache = {}
        for r in items:
            if r['link'] not in cache:
                cache[r['link']] = probe(r['link'])
                time.sleep(2)            # one request per host every 2 s
            code, final = cache[r['link']]
            ok = code.startswith('2') or code.startswith('3')
            moved_home = final.rstrip('/') != r['link'].rstrip('/') and urllib.parse.urlsplit(final).path in ('', '/')
            r['status'] = code + (' (redirects to home page)' if ok and moved_home else '')
            r['status_source'] = f'HEAD check {time.strftime("%Y-%m-%d")}'
            r['suggested_action'] = action(r['link_type'], ok and not moved_home)
            with lock:
                done[0] += 1
                if done[0] % 200 == 0:
                    print(f'{done[0]}/{len(todo)}')
                    write(rows)

    with ThreadPoolExecutor(8) as pool:
        list(pool.map(run_host, by_host.values()))
    write(rows)
    print(f'checked {len(todo)} links on {len(by_host)} hosts')


def counts():
    rows = list(csv.DictReader(open(CSV, encoding='utf-8')))
    print('by type x status:')
    t = defaultdict(Counter)
    for r in rows:
        s = r['status']
        s = {'200': 'alive', '401': 'alive, embedding blocked', '-1': 'no response', 'not checked': 'not checked',
             'host shut down': 'host shut down'}.get(s, 'dead (' + s + ')')
        t[r['link_type']][s] += 1
    for k, c in sorted(t.items(), key=lambda x: -sum(x[1].values())):
        print(f'  {k:10} {sum(c.values()):6}  ' + ', '.join(f'{n} {s}' for s, n in c.most_common()))
    print('by action:', dict(Counter(r['suggested_action'] for r in rows)))
    print('top hosts:')
    for h, n in Counter(r['host'] for r in rows).most_common(25):
        print(f'  {n:6}  {h}')


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'counts'
    lim = int(sys.argv[sys.argv.index('--limit') + 1]) if '--limit' in sys.argv else None
    {'list': build_list, 'check': lambda: check(lim), 'counts': counts}[cmd]()
