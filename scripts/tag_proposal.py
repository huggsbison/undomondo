"""Write docs/tag_proposal.csv: one row per existing tag, saying what it would
become. Proposal only: no post is changed.

Rules, in order:
  1. DROP platform noise and meta tags (soundcloud, youtube, music, photo,
     reblog, misc, Uncategorized ...) and bare year tags (2014): the post
     date already says the year.
  2. Hand-made merges for synonyms, typos and adjective/place pairs
     (hiphop -> hip-hop, scandianavia -> scandinavia, japanese -> japan).
  3. Spelling variants that differ only in case, spaces or hyphens
     (Jazz / jazz, post punk / postpunk) merge into one form.
  Turkish tags (ilerici, geleneksel, ilgincmekan) and his series tags
  (channeling, whiteanger, worldobscure) are kept as they are.

Mersenne's decisions (PR #9, 4 Nov 2026):
  - deneysel merges into experimental.
  - Country pairs use the country noun: japan, france, finland, poland,
    ireland, brasil, UK, ethiopia. Tags with no noun partner (turkish,
    german, american ...) are left alone.
  - Year tags go: every post sits on a year page (archive/2006.html,
    tumblr/2015.html ...) linked from the index pages and from the post itself.

The same mapping applies to WordPress and Tumblr posts, so both eras end up
on one shared tag set.

  python3 scripts/tag_proposal.py
"""
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DROP = {
    'soundcloud': 'platform name', 'vimeo': 'platform name', 'youtube': 'platform name',
    'dailymotion': 'platform name', 'myspace': 'platform name', 'spotify': 'platform name',
    'bandcamp': 'platform name', 'lastfm': 'platform name', 'wikipedia': 'platform name',
    'delicious': 'platform name', 'music': 'says nothing on a music blog',
    'audio': 'post format', 'video': 'post format', 'videos': 'post format',
    'photo': 'Tumblr post type', 'picture': 'post format', 'clips': 'post format',
    'album': 'says nothing', 'misc': 'says nothing', 'other': 'says nothing',
    'uncategorized': 'WordPress default category', 'reblog': 'how it was posted',
    'mp3blog': 'how it was posted', 'height35': 'scrape junk',
}
DECIDED = {'deneysel', 'french', 'british', 'ethio', 'brazil', 'brazilian', 'finnish',
           'polish', 'irish', 'japanese'}
YEAR = re.compile(r'(19|20)\d\d')

MERGE = {
    'hiphop': 'hip-hop', 'postpunk': 'post-punk', 'post punk': 'post-punk',
    'mixes': 'mix', 'edits': 'edit', 're edit': 'edit',
    'musicvideo': 'music video', 'freejazz': 'free jazz', 'progrock': 'prog rock',
    'mathrock': 'math rock', 'easylistening': 'easy listening', 'spaceage': 'space age',
    'space-age': 'space age', 'worldmusic': 'world music', 'middleast': 'middle east',
    'scandianavia': 'scandinavia', 'wintage': 'vintage', 'worldobscurite': 'worldobscure',
    'kraut': 'krautrock', 'brazil': 'brasil', 'brazilian': 'brasil',
    'african': 'africa', 'japanese': 'japan', 'finnish': 'finland', 'french': 'france', 'british': 'UK',
    'ethio': 'ethiopia', 'deneysel': 'experimental',
    'polish': 'poland', 'irish': 'ireland', 'latino': 'latin', 'turk': 'turkish',
    'triphop': 'trip-hop', 'rb': 'r&b', 'guitars': 'guitar', 'minimal-techno': 'minimal techno',
    'micro-house': 'micro house', 'lo fi': 'lo-fi', 'southernrock': 'southern rock',
    'marcribot': 'marc ribot', 'ribot': 'marc ribot', 'dylan': 'bob dylan',
    'classics': 'classic', 'scandinavian': 'scandinavia', 'psych': 'psychedelic',
}


def key(t):
    return re.sub(r'[^a-z0-9&]', '', t.lower())


def main():
    count = defaultdict(Counter)            # tag -> {era: posts}
    for era, name in (('archive', 'wordpress'), ('tumblr', 'tumblr')):
        for p in json.loads((ROOT / era / 'posts.json').read_text(encoding='utf-8')):
            for t in set(p.get('tags') or []):
                count[t][name] += 1

    # rule 3: one spelling per variant group: the most used one (lower case wins a tie)
    groups = defaultdict(list)
    for t in count:
        groups[key(t)].append(t)
    spelling = {}
    for ts in groups.values():
        best = max(ts, key=lambda t: (sum(count[t].values()), t.islower()))
        for t in ts:
            spelling[t] = best

    rows = []
    for t, c in count.items():
        low = t.lower()
        if low in DROP:
            new, why = 'DROP', DROP[low]
        elif YEAR.fullmatch(t):
            new, why = 'DROP', 'year tag: year pages cover it (Mersenne, 4 Nov)'
        elif spelling[t] in MERGE or low in MERGE:
            new = MERGE.get(spelling[t]) or MERGE[low]
            why = 'synonym / typo / same place'
            if low in DECIDED or spelling[t] in DECIDED:
                why = 'Mersenne decision, 4 Nov'
        elif spelling[t] != t:
            new, why = spelling[t], 'same tag, different case or spacing'
        else:
            new, why = t, 'keep'
        if new == t:
            why = 'keep'
        rows.append({'old_tag': t, 'new_tag': new, 'reason': why,
                     'wordpress_posts': c['wordpress'], 'tumblr_posts': c['tumblr'],
                     'total_posts': c['wordpress'] + c['tumblr']})
    rows.sort(key=lambda r: (r['reason'] == 'keep', -r['total_posts'], r['old_tag']))
    (ROOT / 'docs').mkdir(exist_ok=True)
    with open(ROOT / 'docs' / 'tag_proposal.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    after = defaultdict(Counter)
    for r in rows:
        if r['new_tag'] != 'DROP':
            after[r['new_tag']]['wordpress'] += r['wordpress_posts']
            after[r['new_tag']]['tumblr'] += r['tumblr_posts']
    shared = lambda d: sum(1 for c in d.values() if c['wordpress'] and c['tumblr'])
    reasons = Counter(r['reason'] for r in rows)
    print(f'tags now: {len(count)} (shared by both eras: {shared(count)})')
    print(f'tags after: {len(after)} (shared by both eras: {shared(after)})')
    for k, v in reasons.most_common():
        n = sum(r['total_posts'] for r in rows if r['reason'] == k)
        print(f'  {v:4} tags, {n:5} tag uses: {k}')


if __name__ == '__main__':
    main()
