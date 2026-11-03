"""List the posts that are about one specific release, for the album-cover job.

Reads archive/posts.json and tumblr/posts.json (read-only) plus each post's
static page title, and writes:

  docs/missing_covers.csv       high + medium confidence: post names a release
  docs/missing_covers_low.csv   low confidence: artist (and maybe a track) only,
                                no release named. For checking by hand.

and prints counts, including the general posts it skipped (shows, lists,
news, personal posts) by reason.

How it decides, in plain terms:
  - general posts are spotted from the title (radio show, best of, part 3,
    mailbox, netlabel roundup, ...) and skipped
  - the artist is the part of the title before " - ", or the whole title if
    it is short and looks like a name
  - the release is taken from phrases like "(taken from his new album Ears
    on Komfort Music)", 'from their "In case we die" album', 'EP "X"'
  - high   = a release named in the post's opening "(from ... album/EP)"
             line, or in quotes next to album/EP/LP, and an artist in the title
  - medium = a release named elsewhere in the text, or no " - " in the title
  - low    = no release named at all

Nothing here looks anything up online. cover_lookup.py does that.

  python3 scripts/cover_list.py
"""
import csv
import html
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / 'docs'

GENERAL = [
    ('radio show / podcast / own mix', r'radio show|podcast|\bmix\b(?!ed)|mixtape|dj set|\bset\b|undomondo (?:radio|mix|session)'),
    ('list / roundup', r'best of|\btop \d|\bpart\s*\d|\bp\d\b|mailbox|reblog|netlabel|roundup|round-up|selection|recommendation|\blinks?\b|playlist|compilation|\d+ (?:albums|songs|tracks|videos)|mailbag|what the mail|crash course|\bvol\.?\s*\d|#\d'),
    ('video roundup', r'^youtube|videos?\b'),
    ('news / event / personal', r'\bnews\b|festival|concert|\blive (?:at|in)\b|interview|tribute|\bbreak\b|cleaning|holiday|birthday|racism|happy new|announce|\bgig\b|tour|\brip\b|r\.i\.p|dies|passed away|\bblog\b|undomondo|tumblr|update|\?$|!$'),
]
GENERAL = [(why, re.compile(rx, re.I)) for why, rx in GENERAL]

KIND = r'(album|EP|LP|single|12"|7"|mini-album|debut)'
ADJ = r'(?:(?:his|her|their|the|new|debut|latest|forthcoming|upcoming|solo|first|second|2nd|3rd|third|great|excellent|brand new|self-titled)\s+)*'
Q = r'["“”]'   # double quotes only: single quotes clash with apostrophes
ADJ_WORDS = {'debut', 'forthcoming', 'upcoming', 'new', 'latest', 'studio', 'sophomore', 'digital',
             'solo', 'first', 'second', 'third', 'fourth', 'fifth', 'sixth', 'seventh', 'eighth',
             '2nd', '3rd', '4th', '5th', 'full-length', 'full', 'length', 'brand', 'self-titled',
             'released', 'recent', 'upcoming', 'next', 'last', 'great', 'excellent', 'stunning', 'beautiful'}
STOP = {'solo', 'upcoming', 'self-titled', 'recent', 'great', 'on', 'with', 'oriental', 'and',
        'new', 'debut', 'this', 'the', 'a', 'an', 'his', 'her', 'their', 'latest', 'it', 'which',
        'that', 'there', 'same', 'whole', 'full', 'last', 'next', 'previous', 'first', 'second', 'one'}

PATTERNS = [
    # 'album "X"' / 'EP “X”'
    ('quoted after', re.compile(KIND + r'\s*,?\s*(?:called|titled|named)?\s*' + Q + r'([^"“”\n]{2,60}?)' + Q, re.I)),
    # '"X" album'
    ('quoted before', re.compile(Q + r'([^"“”\n]{2,60}?)' + Q + r'\s+' + KIND + r'\b', re.I)),
    # 'from his new album Ears on Komfort Music'
    ('from album X', re.compile(r'from\s+' + ADJ + KIND + r'\s*[-:,]?\s+([^.,;()\n]{2,60}?)\s*(?:\bon\b|\bout\b|\breleased\b|\bvia\b|\bfrom\b|[.,;()\n]|$)', re.I)),
    # 'from their luv 4 the world EP' / 'from his Maritime album on 4AD'
    ('from X album', re.compile(r'from\s+(?:(?:his|her|their|the|new|debut|latest|forthcoming|upcoming|solo)\s+)*([^.,;()\n"“”]{2,50}?)\s+' + KIND + r'\b', re.I)),
]


def clean(s):
    s = html.unescape(re.sub(r'<[^>]+>', ' ', s or ''))
    return re.sub(r'[ \t]+', ' ', s)


def find_release(text):
    """(release, how, where) or None. where = 'opening' if in the first 300 chars."""
    for how, rx in PATTERNS:
        for m in rx.finditer(text):
            groups = [g for g in m.groups() if g]
            name = [g for g in groups if not re.fullmatch(KIND, g, re.I)]
            if not name:
                continue
            name = name[0].strip(' -:"“”\'')
            name = re.sub(r"^(?:19|20)\d\d'?s?\s+", '', name)      # "2004's down by law"
            # "Khruangbin’s debut", "Clinic’s forthcoming seventh": possessive + adjectives only
            name = re.sub(r"^.*?['’]s\s*", '', name) if re.search(r"['’]s\b", name) else name
            name = re.sub(r'^(?:(?:newly|recently|just)\s+)?(?:released|out)\s+', '', name, flags=re.I)
            name = re.sub(r'^(?:(?:' + '|'.join(sorted(ADJ_WORDS)) + r')\s+)+', '', name, flags=re.I)
            name = name.strip(' .-:"“”‘’\'')
            name = re.sub(r"^.*?\w['’]\s+(?=\S)", '', name) if re.search(r"\w['’]\s", name) else name   # "Fennesz’ new"
            if not name or name.lower() in ADJ_WORDS or 'http' in name or re.search(r'\b(?:debut|collaboration|once|had)\b', name, re.I):
                continue
            if re.fullmatch(r"[\d\s']+", name):                   # just a year
                continue
            words = name.lower().split()
            if not words or words[0] in STOP or len(words) > 9 or name.lower() in STOP:
                continue
            if re.search(r'\b(?:is|was|has|have|i|you|we|it\'s|this|which|that|their|his|her|same|recent|myspace)\b', name, re.I):
                continue
            kind = next((g for g in groups if re.fullmatch(KIND, g, re.I)), '')
            where = 'opening' if m.start() < 300 else 'body'
            soft = how == 'from X album' and len(words) == 1 and name.islower()
            if soft:
                how += ', one lowercase word'
            return name, kind.upper() if kind.lower() in ('ep', 'lp') else kind.lower(), how, where
    return None


def page_title(path):
    try:
        h = path.read_text(encoding='utf-8')
    except FileNotFoundError:
        return None
    m = re.search(r'<h1 class="post-title">(.*?)</h1>', h, re.S)
    return html.unescape(re.sub(r'<[^>]+>', '', m.group(1))).strip() if m else None


def main():
    rows, low = [], []
    skipped = Counter()
    for era in ('archive', 'tumblr'):
        posts = json.loads((ROOT / era / 'posts.json').read_text(encoding='utf-8'))
        urlmap = json.loads((ROOT / era / 'urlmap.json').read_text(encoding='utf-8'))
        for p in posts:
            rel = urlmap.get(str(p['id']))
            if era == 'archive':
                rel = f"/archive/{p['year']}/{p['slug']}.html"
            if not rel or not (ROOT / rel.lstrip('/')).exists():
                skipped['no static page'] += 1
                continue
            title = page_title(ROOT / rel.lstrip('/')) or p['title']
            why = next((w for w, rx in GENERAL if rx.search(title)), None)
            if why:
                skipped[why] += 1
                continue
            text = clean(p.get('content'))
            m = re.match(r'\s*(.+?)\s+[-–—]\s+(.+)$', title)
            artist, track = (m.group(1), m.group(2)) if m else (None, None)
            if not artist and len(title.split()) <= 5 and not re.search(r'[:#]', title):
                artist = title
            if not artist:
                skipped['no artist in title'] += 1
                continue
            found = find_release(text)
            row = {'era': 'wordpress' if era == 'archive' else 'tumblr', 'post_path': rel,
                   'post_title': title, 'artist': artist, 'release_title': '', 'release_type': '',
                   'track': track or '', 'confidence': 'low', 'evidence': '',
                   'cover_source_url': '', 'match_note': '', 'cover_confidence': ''}
            if found:
                name, kind, how, where = found
                if re.fullmatch(r'self[ -]titled', name, re.I):
                    name, how = artist, how + ', self-titled'
                elif name.lower() == artist.lower() and track and name.lower() != track.lower():
                    how += ', release name = artist name'
                row.update(release_title=name, release_type=kind, evidence=f'{how} ({where})')
                strong = (how.startswith('quoted') or where == 'opening') and 'lowercase' not in how and 'artist name' not in how
                row['confidence'] = 'high' if (strong and m) else 'medium'
            if row['confidence'] == 'low':
                row['evidence'] = 'no release named in the post'
                low.append(row)
            else:
                rows.append(row)
    DOCS.mkdir(exist_ok=True)
    for name, data in (('missing_covers.csv', rows), ('missing_covers_low.csv', low)):
        with open(DOCS / name, 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=list((rows or low)[0].keys()))
            w.writeheader()
            w.writerows(data)
    c = Counter((r['era'], r['confidence']) for r in rows + low)
    print('about one release:')
    for k in sorted(c):
        print(f'  {c[k]:5}  {k[0]} {k[1]}')
    print('skipped:')
    for k, v in skipped.most_common():
        print(f'  {v:5}  {k}')


if __name__ == '__main__':
    main()
