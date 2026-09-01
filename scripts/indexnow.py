#!/usr/bin/env python3
"""Ping IndexNow (Bing, Yandex, Seznam, Naver) with URLs from the sitemaps.

    ./indexnow.py                 # everything in sitemap.xml
    ./indexnow.py --since 7       # only files changed in the last 7 days
    ./indexnow.py URL [URL ...]   # specific URLs
    ./indexnow.py --dry-run       # show what would be sent

IndexNow takes max 10,000 URLs per request; we batch at 10,000.
A 200 or 202 means accepted. It is a notification, not a guarantee of indexing.
"""
import argparse, glob, json, os, re, subprocess, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
HOST = "www.undomondo.com"
ENDPOINT = "https://api.indexnow.org/IndexNow"

def key():
    files = [f for f in glob.glob(os.path.join(ROOT, "*.txt"))
             if re.fullmatch(r"[0-9a-f]{32}", os.path.basename(f)[:-4] or "")]
    if not files:
        sys.exit("no IndexNow key file at the site root — expected <32-hex>.txt")
    return os.path.basename(files[0])[:-4]

def sitemap_urls():
    urls = []
    for sm in glob.glob(os.path.join(ROOT, "sitemap-*.xml")):
        urls += re.findall(r"<loc>([^<]+)</loc>", open(sm).read())
    return sorted(set(urls))

def changed_since(days):
    """URLs whose backing file was touched by git in the last N days."""
    out = subprocess.run(["git", "-C", ROOT, "log", f"--since={days} days ago",
                          "--name-only", "--pretty=format:"],
                         capture_output=True, text=True).stdout
    files = {f for f in out.split("\n") if f.endswith(".html")}
    urls = set()
    for f in files:
        path = f[:-5]
        path = "" if path == "index" else (path[:-6] if path.endswith("/index") else path)
        urls.add(f"https://{HOST}/{path}".rstrip("/") + ("/" if not path else ""))
    return sorted(u.rstrip("/") if u != f"https://{HOST}/" else u for u in urls)

def submit(urls, k, dry):
    for i in range(0, len(urls), 10000):
        batch = urls[i:i + 10000]
        body = {"host": HOST, "key": k, "keyLocation": f"https://{HOST}/{k}.txt",
                "urlList": batch}
        print(f"batch {i//10000 + 1}: {len(batch)} urls")
        if dry:
            for u in batch[:5]:
                print("   ", u)
            print(f"    … ({len(batch)} total)" if len(batch) > 5 else "")
            continue
        req = urllib.request.Request(
            ENDPOINT, data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json; charset=utf-8"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                print(f"    HTTP {r.status} — {'accepted' if r.status in (200,202) else 'check response'}")
        except urllib.error.HTTPError as e:
            print(f"    HTTP {e.code} — {e.read().decode()[:200]}")

p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
p.add_argument("urls", nargs="*")
p.add_argument("--since", type=int, metavar="DAYS")
p.add_argument("--dry-run", action="store_true")
a = p.parse_args()

k = key()
urls = a.urls or (changed_since(a.since) if a.since else sitemap_urls())
if not urls:
    sys.exit("nothing to submit")
print(f"key {k} · {len(urls)} urls")
submit(urls, k, a.dry_run)
