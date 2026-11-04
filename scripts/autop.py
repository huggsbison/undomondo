"""Give old posts real paragraphs.

Most WordPress-era posts (and a few Tumblr ones) were exported as raw text:
paragraphs separated by blank lines, no <p> tags. WordPress used to add the
tags when it showed a post; the static pages don't, so browsers run the
paragraphs together into one block.

This does what WordPress did (its "autop" step), conservatively:
  - a blank line starts a new paragraph (<p>...</p>)
  - a single newline inside a paragraph becomes <br>
  - block elements (div, iframe, blockquote, lists, headings, tables, hr,
    object/embed) are left exactly as they are and never wrapped in <p>;
    text inside a <blockquote> gets the same treatment
  - posts that already contain a <p> tag are skipped (safe to re-run)

Edits the source JSON and the matching static page together, in place,
like scripts/mp3_relink.py. build_posts.py is NOT used (see cloud-desk
task 02: a full rebuild breaks live pages).

  python3 scripts/autop.py --survey                         # counts only
  python3 scripts/autop.py archive SLUG [SLUG ...]          # WordPress posts by slug
  python3 scripts/autop.py tumblr ID [ID ...]               # Tumblr posts by id
  python3 scripts/autop.py archive --all                    # every affected post
  add --dry-run to print what would change without writing
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOCK = ('div', 'iframe', 'blockquote', 'ul', 'ol', 'table', 'pre', 'object',
         'embed', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'hr', 'p', 'form', 'dl', 'figure')
OPEN = re.compile(r'<(' + '|'.join(BLOCK) + r')\b[^>]*>', re.I)
HAS_P = re.compile(r'<p[\s>]', re.I)
BLANK = re.compile(r'\n[ \t\r]*\n')
VISIBLE = re.compile(r'<[^>]+>')


def match_close(text, tag, start):
    """Index just past the element that opens at `start`, counting nesting."""
    rx = re.compile(r'<(/?)' + tag + r'\b[^>]*>', re.I)
    depth = 0
    for m in rx.finditer(text, start):
        if m.group(0).endswith('/>'):
            if depth == 0:
                return m.end()
            continue
        depth += -1 if m.group(1) else 1
        if depth == 0:
            return m.end()
    return None


def segments(text):
    """Split into ('inline', s) and ('block', s) pieces at the top level."""
    out, pos = [], 0
    while True:
        m = OPEN.search(text, pos)
        if not m:
            out.append(('inline', text[pos:]))
            return out
        tag = m.group(1).lower()
        end = None if tag == 'hr' else match_close(text, tag, m.start())
        if end is None:          # void or unclosed (<hr>, bare <embed>)
            end = m.end()
        out.append(('inline', text[pos:m.start()]))
        out.append(('block', text[m.start():end]))
        pos = end


def paragraphs(s):
    parts = []
    for chunk in BLANK.split(s):
        chunk = chunk.strip()
        if not chunk:
            continue
        if not VISIBLE.sub('', chunk).strip() and '<audio' not in chunk:
            parts.append(chunk)      # stray inline tag with no text: leave bare
            continue
        # a newline straight after an opening inline tag at the start of a
        # paragraph (<strong>\nText) is not a line break: just drop it
        chunk = re.sub(r'^((?:<(?!br\b)[a-z][^>]*>)+)\s+', r'\1', chunk, flags=re.I)
        chunk = re.sub(r'(?<!<br>)\s*\n\s*', '<br>\n', chunk)
        parts.append(f'<p>{chunk}</p>')
    return parts


def autop(text):
    if HAS_P.search(text):
        return text
    out = []
    for kind, s in segments(text):
        if kind == 'inline':
            out += paragraphs(s)
        elif re.match(r'<blockquote\b', s, re.I):
            m = re.match(r'(<blockquote\b[^>]*>)(.*)(</blockquote>)$', s, re.I | re.S)
            if m and BLANK.search(m.group(2)):
                inner = autop(m.group(2))
                out.append(m.group(1) + inner + m.group(3))
            else:
                out.append(s.strip())
        else:
            out.append(s.strip())
    return '\n\n'.join(out)


def needs_fix(text):
    t = (text or '').strip()
    return bool(t) and not HAS_P.search(t) and '\n' in t


# --- static pages -----------------------------------------------------------

START = '<div class="post-content">'
END = re.compile(r'</div>\n\s*<div class="post-(?:tags|nav)">')


def fix_page(path, dry):
    html = path.read_text(encoding='utf-8')
    i = html.find(START)
    m = END.search(html, i)
    if i < 0 or not m:
        return 'no post-content block'
    a = i + len(START)
    body = html[a:m.start()]
    new = autop(body)
    if new == body:
        return 'unchanged'
    if not dry:
        path.write_text(html[:a] + new + html[m.start():], encoding='utf-8')
    return 'fixed'


def page_for(era, post, urlmap):
    if era == 'archive':
        return ROOT / 'archive' / str(post['year']) / f"{post['slug']}.html"
    p = urlmap.get(str(post['id']))
    return ROOT / p.lstrip('/') if p else None


def survey():
    for era in ('archive', 'tumblr'):
        posts = json.loads((ROOT / era / 'posts.json').read_text(encoding='utf-8'))
        c = {'already have <p>': 0, 'blank-line paragraphs, no <p>': 0,
             'single newlines only, no <p>': 0, 'one block, no newlines': 0, 'empty': 0}
        for p in posts:
            t = (p.get('content') or '').strip()
            if not t:
                c['empty'] += 1
            elif HAS_P.search(t):
                c['already have <p>'] += 1
            elif BLANK.search(t):
                c['blank-line paragraphs, no <p>'] += 1
            elif '\n' in t:
                c['single newlines only, no <p>'] += 1
            else:
                c['one block, no newlines'] += 1
        print(f'{era}: {len(posts)} posts')
        for k, v in c.items():
            print(f'  {v:5}  {k}')


def main():
    args = sys.argv[1:]
    if '--survey' in args:
        return survey()
    dry = '--dry-run' in args
    era = args[0]
    want = None if '--all' in args else {a for a in args[1:] if not a.startswith('-')}
    src = ROOT / era / 'posts.json'
    posts = json.loads(src.read_text(encoding='utf-8'))
    urlmap = json.loads((ROOT / era / 'urlmap.json').read_text(encoding='utf-8')) if era == 'tumblr' else {}
    n = 0
    for post in posts:
        key = post['slug'] if era == 'archive' else str(post['id'])
        if want is not None and key not in want:
            continue
        if not needs_fix(post.get('content')):
            continue
        new = autop(post['content'])
        if new == post['content']:
            continue
        page = page_for(era, post, urlmap)
        status = fix_page(page, dry) if page and page.exists() else 'no page'
        print(f'{status:>10}: {page.relative_to(ROOT) if page else key}')
        if status != 'fixed':
            continue            # keep source and page in step
        post['content'] = new
        n += 1
    if not dry and n:
        # keep each file's own layout (archive: one line, tumblr: indent=1)
        indent = 1 if era == 'tumblr' else None
        src.write_text(json.dumps(posts, ensure_ascii=False, indent=indent), encoding='utf-8')
    print(f"{n} post(s) {'would change' if dry else 'changed'}")


if __name__ == '__main__':
    main()
