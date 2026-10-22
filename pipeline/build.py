"""Render the Bioconductor support archive to static files + a Pagefind index.

usage: build.py <public.sqlite> <out_dir> [--force]

Incremental: a manifest of content hashes (<out_dir>/.manifest.json) means only
changed pages are rewritten, pages for removed threads are deleted, and the
Pagefind index is rebuilt only when some page changed. Search fields come from
data-pagefind-* attributes in the thread pages; the Pagefind CLI indexes them.

URLs use the post `uid` (what support.bioconductor.org exposed), not the internal id.
All generated links are root-relative, so the output works on any host.
"""

import hashlib
import html
import json
import re
import shutil
import sqlite3
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

TYPES = {0: "Question", 1: "Answer", 2: "Job", 6: "Comment", 8: "Tutorial", 11: "News"}
MIN_TAG_FILTER = 50  # ponytail: only common tags become search filters; 11k tags would swamp the filter list
OLD_HOST = re.compile(r"https?://(?:www\.)?support\.bioconductor\.org(?=[/\"'?#<\s]|$)", re.I)
e = html.escape
CSS = Path(__file__).with_name("style.css").read_text()
CSS_PATH = f"style.{hashlib.sha256(CSS.encode()).hexdigest()[:10]}.css"  # fingerprinted: browsers may cache forever


def rewrite_links(s):
    """Absolute links to the old site become root-relative."""
    return OLD_HOST.sub("", s)


def page(title, body, extra_head=""):
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)} | Bioconductor Support (archive)</title>
<link rel="stylesheet" href="/{CSS_PATH}">{extra_head}
</head><body>
<header><a class="brand" href="/">Bioconductor Support <span>archive</span></a>
<form action="/search/" method="get"><input type="search" name="q" placeholder="Search the archive" aria-label="Search the archive"></form></header>
<main>{body}</main>
<footer>Read-only archive of support.bioconductor.org (2002&ndash;2026).</footer>
</body></html>"""


class Site:
    def __init__(self, db_path):
        con = sqlite3.connect(db_path)
        con.row_factory = sqlite3.Row
        self.users = {r["id"]: r for r in con.execute('SELECT * FROM "user"')}
        self.posts = con.execute("SELECT * FROM post ORDER BY id").fetchall()
        self.by_id = {p["id"]: p for p in self.posts}
        self.children = defaultdict(list)
        for p in self.posts:
            if not p["is_toplevel"]:
                self.children[p["parent_id"]].append(p)
        self.roots = [p for p in self.posts if p["is_toplevel"]]
        self.filter_tags = {r[0] for r in con.execute(
            "SELECT tag FROM post_tag t JOIN post p ON p.id = t.post_id WHERE p.is_toplevel "
            "GROUP BY tag HAVING count(*) >= ?", (MIN_TAG_FILTER,))}

    def byline(self, p):
        u = self.users.get(p["author_id"])
        name = e(u["name"] if u else "unknown")
        return f'<div class="byline" data-pagefind-ignore>{name} &middot; <time>{p["creation_date"][:10]}</time> &middot; {p["vote_count"]} votes</div>'

    def render_post(self, p):
        kind = TYPES.get(p["type"], "Post")
        accepted = " accepted" if p["type"] == 1 and p["accept_count"] else ""
        kids = self.children[p["id"]]
        if p["type"] != 6:  # under a question/answer: answers first, accepted then by votes
            kids = sorted(kids, key=lambda c: (c["type"] != 1, -(c["accept_count"] > 0), -c["vote_count"], c["id"]))
        inner = "".join(self.render_post(c) for c in kids)
        return (f'<article id="{p["uid"]}" class="post {kind.lower()}{accepted}">'
                f'<div class="kind" data-pagefind-ignore><a href="#{p["uid"]}">{kind}</a>{" &#10003; accepted" if accepted else ""}</div>'
                f'<div class="content">{rewrite_links(p["html"])}</div>{self.byline(p)}'
                f'{f"<div class=children>{inner}</div>" if inner else ""}</article>')

    def thread_page(self, r):
        tags = "".join(f'<span class="tag"{" data-pagefind-filter=tag" if t in self.filter_tags else ""}>{e(t)}</span>'
                       for t in r["tags"].split(",") if t)
        date = r["creation_date"][:10]
        meta = (f'<p class="meta" data-pagefind-ignore><span data-pagefind-filter="type">{TYPES.get(r["type"], "Post")}</span>'
                f' &middot; <time data-pagefind-filter="year:{date[:4]}" data-pagefind-meta="date:{date}">{date}</time>'
                f' &middot; {r["answer_count"]} answers &middot; {r["view_count"]} views</p>')
        return page(r["title"], f'<div data-pagefind-body><h1>{e(r["title"])}</h1>{meta}'
                                f'<div class="tags" data-pagefind-ignore="index">{tags}</div>{self.render_post(r)}</div>')

    def listing(self, rows):
        return "<ol class=listing>" + "".join(
            f'<li><a href="/p/{r["uid"]}/">{e(r["title"])}</a> <small>{r["creation_date"][:10]} &middot; '
            f'{r["thread_votecount"]} votes &middot; {r["answer_count"]} answers</small></li>' for r in rows) + "</ol>"

    def pages(self):
        """Yield (relative path, text) for every output file except the Pagefind index."""
        for r in self.roots:
            yield f"p/{r['uid']}/index.html", self.thread_page(r)
        redirects = {p["uid"]: self.by_id[p["root_id"]]["uid"] for p in self.posts if not p["is_toplevel"]}
        yield "redirects.json", json.dumps(redirects, separators=(",", ":"))
        top = sorted(self.roots, key=lambda r: -r["thread_votecount"])[:100]
        recent = sorted(self.roots, key=lambda r: r["creation_date"], reverse=True)[:50]
        yield "index.html", page("Home",
            f"<h1>Bioconductor Support archive</h1><p>{len(self.roots):,} threads, {len(self.posts):,} posts. "
            f'<a href="/search/">Search the archive</a>.</p>'
            f"<h2>Most voted threads</h2>{self.listing(top)}<h2>Most recent threads</h2>{self.listing(recent)}")
        yield "search/index.html", page("Search", '<h1>Search</h1><div id="search"></div>', """
<link rel="stylesheet" href="/pagefind/pagefind-ui.css"><script src="/pagefind/pagefind-ui.js"></script>
<script>addEventListener("DOMContentLoaded", () => {
  const ui = new PagefindUI({ element: "#search", showSubResults: false, showImages: false });
  const q = new URLSearchParams(location.search).get("q"); if (q) ui.triggerSearch(q);
});</script>""")
        yield "404.html", page("Not found", "<h1>Not found</h1><p>That page is not in the archive.</p>")
        yield CSS_PATH, CSS

def write_index(site_dir):
    # ponytail: Pagefind's Python API costs a flat 0.1 s per record (80 min here); the CLI is parallel
    shutil.rmtree(site_dir / "pagefind", ignore_errors=True)
    subprocess.run([sys.executable, "-m", "pagefind", "--site", str(site_dir)], check=True)


def main(db_path, out, force=False):
    out = Path(out)
    manifest_path = out / ".manifest.json"
    old = {} if force or not manifest_path.exists() else json.loads(manifest_path.read_text())
    new, changed = {}, 0
    site = Site(db_path)
    for rel, text in site.pages():
        h = hashlib.sha256(text.encode()).hexdigest()
        new[rel] = h
        path = out / rel
        if old.get(rel) != h or not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
            changed += 1
    removed = old.keys() - new.keys()
    for rel in removed:
        (out / rel).unlink(missing_ok=True)
    print(f"{len(site.roots)} threads: {changed} files written, {len(removed)} removed")
    if changed or removed or not (out / "pagefind").exists():
        print("rebuilding search index")
        write_index(out)
    else:
        print("search index up to date")
    # BUILD_ID keys the Worker's edge cache: a new ID busts every cached response at once.
    build_id = hashlib.sha256(json.dumps(new, sort_keys=True).encode()).hexdigest()[:12]
    (out / "BUILD_ID").write_text(build_id)
    print(f"BUILD_ID {build_id}")
    manifest_path.write_text(json.dumps(new))  # last, so an interrupted build redoes everything


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--force"]
    main(*args, force="--force" in sys.argv)
