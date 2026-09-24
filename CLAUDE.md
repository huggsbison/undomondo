# undomondo.com

Static site for **Undomondo**: a music blog, radio show and DJ outlet running since 2005. It's owned by Mersenne. Always call him Mersenne, never Palomino. He's based in Barcelona. He's not a web developer, so explain tech choices in plain language.

Usually this file gets read by a Claude Code cloud session. That session can't see Mersenne's Mac, his memory files or his Obsidian vault, so everything it needs to know is written here.

## How it deploys

- Repo `huggsbison/undomondo`. Netlify auto-deploys `main` on every push, so **a push to main goes straight to the live site.**
- Never push to `main` yourself. Work on a branch and open a PR. He merges it. The same goes for anything that touches `_redirects` or DNS.
- Locally he deploys with `./deploy.sh`, which does add-all, commit and push. That's his command. Don't run it from a cloud session.
- No build step on Netlify. The repo is the published folder, and every file in it is public. Keep secrets and private notes out of it.

## Layout

| Path | What |
|---|---|
| `index.html` | Home page |
| `archive/` | WordPress era, 2005–2008, 646 posts. `posts.json` is the source, and year pages plus `{year}/{slug}.html` are generated from it |
| `tumblr/` | Tumblr era, 2007 onward. Same pattern: `posts.json` → year pages + static post pages |
| `archive/urlmap.json`, `tumblr/urlmap.json` | old post ID → new path. The redirects are built from these |
| `assets/post.css` | Shared post-page CSS |
| `scripts/build_posts.py` | Regenerates every static post page, the sitemaps, `robots.txt` and `llms.txt`. Python 3 stdlib only, safe to re-run. `--pilot` builds a ~20-post sample |
| `scripts/rewrite_year_pages.py` | Rewrites the year index pages |
| `scripts/indexnow.py` | Pings Bing/IndexNow. `--dry-run` first. Might be blocked by the cloud network |
| `_redirects` | Netlify redirects (feeds → Substack, old Tumblr URLs → new pages) |
| `landing/`, `index-old*.html`, `*.bak`, `ARCHIVE_*.md`, `HANDOFF-*.md` | Workshop leftovers. Don't build on them |

Generated pages are outputs. Fix the generator or the JSON, then regenerate. Don't hand-edit 3,000 HTML files.

## Settled decisions (don't reopen)

- **Old Tumblr subdomain is being cut.** `tumblr.undomondo.com` duplicates the new `/tumblr/` pages and outranks them. `_redirects` already has 3,419 host rules (301 to the new page) plus a catch-all to `/tumblr/`. Those rules do nothing until DNS moves, and the DNS flip is Mersenne's to do. **Leave Tumblr's own custom-domain setting alone.**
- **504 old Tumblr posts are missing on purpose.** They came out mangled by the scrape and were removed. Don't rebuild them or report them as a bug. Their old URLs go to `/tumblr/`.
- The indexing setup is done: Bing domain property, sitemaps, IndexNow. If search traffic is low, look at the duplicate subdomain first, not at crawling.
- Newsletter feeds (`/feed`, `/rss.xml`) 301 to Substack on purpose.

## Design system

- **Fonts** (Google Fonts): Dela Gothic One for display, Fugaz One for the logo, Space Mono for mono/labels, DM Sans for body. Merriweather is used for long-form post text.
- **Colors**: tomato `#D62828`, cream `#F2EFE5`, charcoal `#111`, blue `#005F99`, golden `#FFB703`.
- **Patterns**: halftone-blue sections, grain overlay, dot patterns.
- **Layout**: fixed sidebar with numbered nav on desktop, top nav on mobile.
- Match what's already there. Don't add new fonts, colors or frameworks. **Show a mockup before building anything visual.** A screenshot or a preview branch is fine.

## Music facts

Never write a release date, label, track count, running order or guest credit from memory. Mersenne's Spotify lookup script lives on his Mac, not here. If a fact can't be checked, leave a visible `TODO: verify` and tell him. Guessing is worse.

## Writing (any copy that ships on the site, plus PR descriptions)

- Direct, no fluff, have an opinion. He wants real feedback, not sugar-coating.
- Say a thing once. No restating a sentence in a shorter punchy one.
- No "X, not Y" antitheses. Say the positive half and drop the rest.
- No hedges: "It's worth noting", "Interestingly", "Importantly". No "Furthermore/Moreover/Additionally".
- Headers name the subject ("Tumblr redirects"). They never announce what's coming ("What this means", "The part that matters").
- No bolded thesis sentences sitting on top of paragraphs. Bold goes on a term, a number or a name.
- No em dashes in titles. Use a colon.
- Contractions are fine. Vary sentence length. Don't end on an inspirational climax.
- One idea per paragraph. Plain words over abstractions.

## Working with him

- Act first and skip the recaps. Don't narrate tool calls.
- One build at a time. If a task starts sprawling, finish or park the current one first.
- When done, give a short summary: what changed, the PR link, and anything he has to do himself (merge, DNS, Netlify settings).
