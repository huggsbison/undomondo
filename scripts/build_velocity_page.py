#!/usr/bin/env python3
"""Turn the Velocity essay markdown into one standalone, unlisted HTML page.

Usage:
    build_velocity_page.py <essay.md> <out.html>            final build, refuses leftover markup
    build_velocity_page.py <essay.md> <out.html> --preview  resolves open markup, adds a banner
"""
import html
import re
import sys

TITLE = "Velocity Is Eating Itself"


def strip_todo_box(text):
    lines = text.split("\n")
    while lines and (lines[0].startswith(">") and "…my concern" not in lines[0] or not lines[0].strip()):
        lines.pop(0)
    return "\n".join(lines)


def resolve_preview(text):
    """Preview only: take each proposal, drop struck text and bare tags."""
    def swap(m):
        new = m.group(2).strip()
        return "" if new.startswith("cut") else new
    # struck text followed by one or more proposals: keep the last proposal
    text = re.sub(r"~~[^~]+~~ (?:==\[[^\]]*\] [^=]+== )*==\[[^\]]*\] ([^=]+)==",
                  lambda m: "" if m.group(1).strip().startswith("cut") else m.group(1).strip(), text)
    text = re.sub(r" ?==\[[^\]]*\]==", "", text)          # bare tags
    text = re.sub(r"==\[[^\]]*\] ([^=]+)==", r"\1", text)  # tagged additions
    text = text.replace("==", "")
    return re.sub(r"(?<=\S)  +", " ", text)


def inline(s):
    s = html.escape(s, quote=False)
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', s)
    s = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", s)
    return s


def to_html(text):
    out, quote = [], []

    def flush_quote():
        if quote:
            body, cite = quote[0], (quote[1] if len(quote) > 1 else "")
            cite = re.sub(r"^—\s*", "", cite)
            out.append(f'<blockquote class="epigraph"><p>{inline(body)}</p>'
                       + (f"<cite>{inline(cite)}</cite>" if cite else "") + "</blockquote>")
            quote.clear()

    for block in re.split(r"\n\s*\n", text.strip()):
        block = block.strip()
        if not block:
            continue
        if block.startswith(">"):
            quote.extend(l.lstrip("> ").strip() for l in block.split("\n") if l.lstrip("> ").strip())
            flush_quote()
        elif block == "---":
            if any(o.startswith(("<p>", "<h2>")) for o in out):  # no rule between the epigraph and the first line
                out.append('<hr>')
        elif block.startswith("### "):
            out.append(f'<h3>{inline(block[4:])}</h3>')
        elif block.startswith("## "):
            out.append(f'<h2>{inline(block[3:])}</h2>')
        elif re.fullmatch(r"\*[^*].*\*", block) and "\n" not in block:
            out.append(f'<p class="meta">{inline(block[1:-1])}</p>')
        else:
            out.append(f"<p>{inline(' '.join(block.split()))}</p>")
    return "\n".join(out)


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow, noarchive">
<meta name="color-scheme" content="dark">
<meta name="theme-color" content="#0B2233">
<title>{title}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Anton&family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,600;1,6..72,400&family=Space+Mono:ital@0;1&display=swap" rel="stylesheet">
<style>
:root {{ --bg:#0B2233; --ink:#EDE9DC; --soft:#8fa6b5; --accent:#FFB703; --rule:#1e3b4f; }}
* {{ box-sizing:border-box; }}
html {{ -webkit-text-size-adjust:100%; }}
body {{ margin:0; background:var(--bg); color:var(--ink);
  font:400 1.3125rem/1.62 "Newsreader", Georgia, serif; }}
main {{ max-width:39rem; margin:0 auto; padding:4.5rem 1.25rem 6rem; }}
.kicker {{ font:400 .75rem/1 "Space Mono", monospace; letter-spacing:.14em; text-transform:uppercase; color:var(--accent); margin:0 0 1.5rem; }}
h1 {{ font:400 clamp(2.7rem, 10.5vw, 4.6rem)/1 "Anton", Impact, sans-serif; text-transform:uppercase; margin:0 0 1.25rem; letter-spacing:.005em; text-wrap:balance; }}
.byline {{ font:400 .8125rem/1.5 "Space Mono", monospace; color:var(--soft); margin:0 0 3.5rem; }}
blockquote.epigraph {{ margin:0 0 3rem; padding:0 0 0 1.1rem; border-left:3px solid var(--accent); }}
blockquote.epigraph p {{ margin:0 0 .5rem; font-style:italic; }}
blockquote.epigraph cite {{ font:400 .8125rem/1.5 "Space Mono", monospace; color:var(--soft); font-style:normal; }}
p {{ margin:0 0 1.35em; }}
h2 {{ font:400 .9375rem/1 "Space Mono", monospace; color:var(--accent); text-align:center; margin:3.75rem 0 2rem; letter-spacing:.1em; }}
h3 {{ font:400 .75rem/1 "Space Mono", monospace; letter-spacing:.14em; text-transform:uppercase; color:var(--soft); margin:2.5rem 0 1rem; }}
h3 + p {{ font-size:1.0625rem; line-height:1.6; color:var(--soft); }}
hr {{ border:0; height:1px; background:var(--rule); margin:3rem auto; width:5rem; }}
a {{ color:inherit; text-decoration:underline; text-decoration-color:var(--accent); text-decoration-thickness:1.5px; text-underline-offset:.18em; }}
a:hover {{ color:var(--accent); }}
p.meta {{ font:400 .8125rem/1.6 "Space Mono", monospace; color:var(--soft); margin:0 0 .5em; }}
.preview {{ font:400 .75rem/1.5 "Space Mono", monospace; background:var(--accent); color:#fff; padding:.5rem 1rem; text-align:center; }}
@media (max-width:30rem) {{ body {{ font-size:1.1875rem; }} main {{ padding-top:3rem; }} }}
</style>
</head>
<body>
{banner}<main>
<h1>{title}</h1>
<p class="byline">Mersenne / Undomondo · 2026 · about {minutes} min</p>
{body}
</main>
</body>
</html>
"""


def main():
    src, dst = sys.argv[1], sys.argv[2]
    preview = "--preview" in sys.argv
    text = strip_todo_box(open(src, encoding="utf-8").read())
    if preview:
        text = resolve_preview(text)
    elif "==" in text or "~~" in text:
        sys.exit("Leftover ==highlight== or ~~strike~~ marks in the essay. Finish the text first.")
    # the byline moves to the top of the page, so drop it from the foot
    text = re.sub(r"\n\*Mersenne / Undomondo, 2026\*\n", "\n", text)
    words = len(re.sub(r"\(https?://\S+\)", "", text.split("### Notes")[0]).split())
    banner = '<div class="preview">PREVIEW · text not final · open items shown as proposed</div>\n' if preview else ""
    open(dst, "w", encoding="utf-8").write(
        PAGE.format(title=TITLE, body=to_html(text), banner=banner, minutes=max(1, round(words / 230))))
    print(f"{dst}: {words} words")


if __name__ == "__main__":
    main()
