"""Find a cover URL for each high-confidence row of docs/missing_covers.csv.

Fills cover_source_url, match_note and cover_confidence in place. It only
records URLs; it downloads no images.

Order of sources, per the brief:
  1. MusicBrainz release-group search + Cover Art Archive front image
  2. iTunes Search API (album artwork, 600 px)
  Bandcamp has no public search API, so rows with no match get a note
  to check Bandcamp by hand.

A match needs the artist name and the release title to agree after
lower-casing and stripping punctuation; the year (when MusicBrainz or iTunes
gives one) goes in match_note so you can check it against the post date.
  cover_confidence high   = artist + title match exactly
  cover_confidence medium = one side matches exactly, the other loosely

Polite: one request per second to MusicBrainz (their rule), a named
User-Agent, and nothing in parallel.

NOT TESTED against the live APIs: the cloud session that wrote it had those
hosts blocked. Run it where the network is open (your Mac is fine):

  python3 scripts/cover_lookup.py --limit 5     # try a few rows first
  python3 scripts/cover_lookup.py               # all high-confidence rows
"""
import csv
import json
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSV = ROOT / 'docs' / 'missing_covers.csv'
UA = 'undomondo-covers/1.0 ( https://www.undomondo.com )'


def get_json(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def exists(url):
    req = urllib.request.Request(url, method='HEAD', headers={'User-Agent': UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status < 400
    except Exception:
        return False


def norm(s):
    s = unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode().lower()
    s = re.sub(r'\b(the|a|an)\b', ' ', s)
    return re.sub(r'[^a-z0-9]+', '', s)


def close(a, b):
    a, b = norm(a), norm(b)
    return bool(a and b) and (a in b or b in a)


def musicbrainz(artist, title):
    q = f'releasegroup:"{title}" AND artist:"{artist}"'
    url = 'https://musicbrainz.org/ws/2/release-group/?fmt=json&limit=5&query=' + urllib.parse.quote(q)
    data = get_json(url)
    time.sleep(1.1)
    for rg in data.get('release-groups', []):
        mb_artist = ''.join(c.get('name', '') + c.get('joinphrase', '') for c in rg.get('artist-credit', []))
        t_ok = norm(rg['title']) == norm(title)
        a_ok = norm(mb_artist) == norm(artist)
        if not ((t_ok or close(rg['title'], title)) and (a_ok or close(mb_artist, artist))):
            continue
        cover = f"https://coverartarchive.org/release-group/{rg['id']}/front-500"
        if not exists(cover):
            continue
        year = (rg.get('first-release-date') or '')[:4]
        note = f"MusicBrainz: {mb_artist} - {rg['title']} ({year or 'no year'}, {rg.get('primary-type', '?')})"
        return cover, note, 'high' if (t_ok and a_ok) else 'medium'
    return None


def itunes(artist, title):
    term = urllib.parse.quote(f'{artist} {title}')
    data = get_json(f'https://itunes.apple.com/search?entity=album&limit=10&term={term}')
    time.sleep(1.1)
    for r in data.get('results', []):
        t_ok = norm(r.get('collectionName')) == norm(title)
        a_ok = norm(r.get('artistName')) == norm(artist)
        if not ((t_ok or close(r.get('collectionName'), title)) and (a_ok or close(r.get('artistName'), artist))):
            continue
        art = (r.get('artworkUrl100') or '').replace('100x100bb', '600x600bb')
        if not art:
            continue
        year = (r.get('releaseDate') or '')[:4]
        note = f"iTunes: {r['artistName']} - {r['collectionName']} ({year or 'no year'})"
        return art, note, 'high' if (t_ok and a_ok) else 'medium'
    return None


def main():
    limit = int(sys.argv[sys.argv.index('--limit') + 1]) if '--limit' in sys.argv else None
    rows = list(csv.DictReader(open(CSV, encoding='utf-8')))
    done = 0
    for row in rows:
        if row['confidence'] != 'high' or row['cover_source_url']:
            continue
        if limit is not None and done >= limit:
            break
        done += 1
        row['match_note'] = ''
        hit = None
        for source in (musicbrainz, itunes):
            try:
                hit = source(row['artist'], row['release_title'])
            except Exception as e:
                row['match_note'] = f'{source.__name__} error: {e}'
            if hit:
                break
        if hit:
            row['cover_source_url'], row['match_note'], row['cover_confidence'] = hit
        else:
            row['match_note'] = row['match_note'] or 'no match on MusicBrainz or iTunes; check Bandcamp by hand'
            row['cover_confidence'] = 'low'
        print(f"{row['cover_confidence']:>6}  {row['artist']} - {row['release_title']}")
    with open(CSV, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


if __name__ == '__main__':
    main()
