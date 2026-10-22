"""Render the Bioconductor support archive to static files + a Pagefind index.

usage: build.py <public.sqlite> <out_dir> [--force] [--sample N]

--sample N renders only the N most-voted and N most-recent threads, for fast design iteration.

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
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote

TYPES = {0: "Question", 1: "Answer", 2: "Job", 6: "Comment", 8: "Tutorial", 11: "News"}
MIN_TAG_FILTER = 50  # ponytail: only common tags become search filters; 11k tags would swamp the filter list
OLD_HOST = re.compile(r"https?://(?:www\.)?support\.bioconductor\.org(?=[/\"'?#<\s]|$)", re.I)
e = html.escape
CSS = Path(__file__).with_name("style.css").read_text()
CSS_PATH = f"style.{hashlib.sha256(CSS.encode()).hexdigest()[:10]}.css"  # fingerprinted: browsers may cache forever


def rewrite_links(s):
    """Absolute links to the old site become root-relative."""
    return OLD_HOST.sub("", s)


# Bioconductor's GA4 property (same as bioconductor.org); production hostname only, so demos and local builds don't count.
ANALYTICS = """
<script>if (location.hostname === "support.bioconductor.org") {
  const s = document.createElement("script"); s.async = true;
  s.src = "https://www.googletagmanager.com/gtag/js?id=G-WJMEEH1J58"; document.head.append(s);
  window.dataLayer = window.dataLayer || []; window.gtag = function () { dataLayer.push(arguments); };
  gtag("js", new Date()); gtag("config", "G-WJMEEH1J58");
}</script>"""
SEARCH_HEAD = """
<link rel="stylesheet" href="/pagefind/pagefind-component-ui.css">
<script src="/pagefind/pagefind-component-ui.js" type="module"></script>"""


def page(title, body, extra_head="", wide=False):
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)} | Bioconductor Support archive</title>
<link rel="stylesheet" href="/{CSS_PATH}">{ANALYTICS}{SEARCH_HEAD}{extra_head}
</head><body>
<header class="site"><div class="wrap">
<a class="brand" href="/"><span class="b1">Bioconductor</span> <span class="b2">Support</span> <span class="pill">archive</span></a>
<nav><a href="/">Home</a><a href="/search/">Search</a>
<pagefind-modal-trigger instance="modal" placeholder="Search the archive"></pagefind-modal-trigger></nav>
</div></header>
<pagefind-modal instance="modal"></pagefind-modal>
<div class="notice"><div class="wrap">This is a read-only archive of support.bioconductor.org (2002&ndash;2026). Posting and accounts are closed.</div></div>
<main class="wrap{' wide' if wide else ''}">{body}</main>
<footer class="wrap">Bioconductor Support archive &middot; content contributed by the Bioconductor community</footer>
</body></html>"""


def num(n):
    return f"{n:,}"


class Site:
    def __init__(self, db_path, sample=0):
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
        if sample:
            keep = {r["id"] for r in sorted(self.roots, key=lambda r: -r["thread_votecount"])[:sample]}
            keep |= {r["id"] for r in sorted(self.roots, key=lambda r: r["creation_date"])[-sample:]}
            self.roots = [r for r in self.roots if r["id"] in keep]
            self.posts = [p for p in self.posts if p["root_id"] in keep]  # ponytail: tag counts stay full-archive
        self.tag_counts = con.execute(
            "SELECT tag, count(*) n FROM post_tag t JOIN post p ON p.id = t.post_id WHERE p.is_toplevel "
            "GROUP BY tag HAVING count(*) >= ? ORDER BY n DESC", (MIN_TAG_FILTER,)).fetchall()
        self.filter_tags = {r["tag"] for r in self.tag_counts}

    def tag_link(self, t, extra=""):
        q = f"tag={quote(t)}" if t in self.filter_tags else f"q={quote(t)}"
        return f'<a class="tag" href="/search/?{q}">{e(t)}{extra}</a>'

    def author(self, p):
        u = self.users.get(p["author_id"])
        return e(u["name"] if u else "unknown")

    def collect(self, p, anchor, answers, comments):
        """Answers anywhere in the thread become cards; comments attach to the nearest card above them."""
        for c in self.children[p["id"]]:
            if c["type"] == 6:
                comments[anchor].append(c)
                self.collect(c, anchor, answers, comments)
            else:
                answers.append(c)
                self.collect(c, c["id"], answers, comments)

    def card(self, p, comments):
        accepted = p["type"] == 1 and p["accept_count"] > 0
        cs = "".join(
            f'<li id="{c["uid"]}"><div class="content">{rewrite_links(c["html"])}</div>'
            f'<span class="who">&mdash; {self.author(c)}, <time>{c["creation_date"][:10]}</time></span></li>'
            for c in sorted(comments[p["id"]], key=lambda c: c["id"]))
        return (f'<article id="{p["uid"]}" class="post{" accepted" if accepted else ""}">'
                f'<div class="votes" data-pagefind-ignore><span class="n">{p["vote_count"]}</span><span class="l">votes</span>'
                f'{"<span class=check title=Accepted aria-label=Accepted>&#10003;</span>" if accepted else ""}</div>'
                f'<div class="body"><div class="content">{rewrite_links(p["html"])}</div>'
                f'<div class="byline" data-pagefind-ignore><a href="#{p["uid"]}">{TYPES.get(p["type"], "Post").lower()}</a>'
                f' by <b>{self.author(p)}</b> &middot; <time>{p["creation_date"][:10]}</time></div>'
                f'{f"<ul class=comments data-pagefind-ignore=index>{cs}</ul>" if cs else ""}</div></article>')

    def thread_page(self, r):
        answers, comments = [], defaultdict(list)
        self.collect(r, r["id"], answers, comments)
        answers.sort(key=lambda a: (-(a["accept_count"] > 0), -a["vote_count"], a["id"]))
        tags = [t for t in r["tags"].split(",") if t]
        kind, date = TYPES.get(r["type"], "Post"), r["creation_date"][:10]
        hidden = "".join([
            f'<span hidden data-pagefind-filter="type">{kind}</span>',
            f'<span hidden data-pagefind-filter="year">{date[:4]}</span>',
            *(f'<span hidden data-pagefind-filter="tag">{e(t)}</span>' for t in tags if t in self.filter_tags),
            f'<span hidden data-pagefind-meta="date">{date}</span>',
            f'<span hidden data-pagefind-meta="type">{kind}</span>',
            f'<span hidden data-pagefind-meta="answers">{len(answers)}</span>',
        ])
        head = f"{len(answers)} answer{'s' if len(answers) != 1 else ''}"
        side = (f'<aside><dl><dt>Asked</dt><dd>{date}</dd><dt>Type</dt><dd>{kind}</dd>'
                f'<dt>Answers</dt><dd>{len(answers)}</dd><dt>Views</dt><dd>{num(r["view_count"])}</dd>'
                f'<dt>Votes</dt><dd>{r["thread_votecount"]}</dd></dl>'
                f'<div class="tags">{"".join(self.tag_link(t) for t in tags)}</div></aside>')
        body = (f'<div class="thread" data-pagefind-body>{hidden}<h1>{e(r["title"])}</h1>{self.card(r, comments)}'
                f'{f"<h2 class=answers-head data-pagefind-ignore>{head}</h2>" if answers else ""}'
                f'{"".join(self.card(a, comments) for a in answers)}</div>')
        return page(r["title"], f'<div class="layout">{body}{side}</div>', wide=True)

    def listing(self, rows):
        return "<ol class=listing>" + "".join(
            f'<li><a href="/p/{r["uid"]}/">{e(r["title"])}</a><small>{r["creation_date"][:10]} &middot; '
            f'{r["thread_votecount"]} votes &middot; {r["answer_count"]} answers</small></li>' for r in rows) + "</ol>"

    def pages(self):
        """Yield (relative path, text) for every output file except the Pagefind index."""
        for r in self.roots:
            yield f"p/{r['uid']}/index.html", self.thread_page(r)
        redirects = {p["uid"]: self.by_id[p["root_id"]]["uid"] for p in self.posts if not p["is_toplevel"]}
        yield "redirects.json", json.dumps(redirects, separators=(",", ":"))
        top = sorted(self.roots, key=lambda r: -r["thread_votecount"])[:50]
        recent = sorted(self.roots, key=lambda r: r["creation_date"], reverse=True)[:50]
        tags = "".join(self.tag_link(r["tag"], f'<span class=count>{num(r["n"])}</span>') for r in self.tag_counts[:60])
        yield "index.html", page("Home", f"""
<section class="hero"><h1>Bioconductor Support archive</h1>
<p>{num(len(self.roots))} questions and {num(len(self.posts) - len(self.roots))} answers and comments from the
Bioconductor community, 2002&ndash;2026.</p>
<form action="/search/" method="get"><input type="search" name="q" placeholder="Search, e.g. DESeq2 lfcShrink" aria-label="Search the archive">
<button>Search</button></form></section>
<section><h2>Popular tags</h2><div class="tags">{tags}</div></section>
<div class="columns"><section><h2>Most voted</h2>{self.listing(top)}</section>
<section><h2>Most recent</h2>{self.listing(recent)}</section></div>""")
        yield "search/index.html", page("Search", f"""
<h1>Search</h1>
<pagefind-config faceted excerpt-length="40"></pagefind-config>
<pagefind-input placeholder="Search {num(len(self.roots))} threads" autofocus></pagefind-input>
<div class="filters">
<pagefind-filter-dropdown filter="type" label="Type"></pagefind-filter-dropdown>
<pagefind-filter-dropdown filter="year" label="Year" sort="alphabetical"></pagefind-filter-dropdown>
<pagefind-filter-dropdown filter="tag" label="Tag" sort="count-desc"></pagefind-filter-dropdown>
</div>
<pagefind-summary></pagefind-summary>
<pagefind-results><script type="text/pagefind-template">
<li class="result"><a class="result-title" href="{{{{ meta.url | default(url) | safeUrl }}}}">{{{{ meta.title }}}}</a>
<div class="result-meta">{{{{ meta.type }}}} &middot; {{{{ meta.date }}}} &middot; {{{{ meta.answers }}}} answers</div>
{{{{#if excerpt}}}}<p class="result-excerpt">{{{{+ excerpt +}}}}</p>{{{{/if}}}}</li>
</script></pagefind-results>
<script type="module">
// Keep ?q= and ?tag= in sync with the search, so searches can be linked and bookmarked.
await customElements.whenDefined("pagefind-input");
const search = window.PagefindComponents.getInstanceManager().getInstance("default");
const params = new URLSearchParams(location.search);
const q = params.get("q") ?? "", tags = params.getAll("tag");
if (q || tags.length) search.triggerSearchWithFilters(q, tags.length ? {{ tag: tags }} : {{}});
search.on("search", (term, filters) => {{
  const u = new URL(location.href); u.search = "";
  if (term) u.searchParams.set("q", term);
  for (const t of filters?.tag ?? []) u.searchParams.append("tag", t);
  history.replaceState(null, "", u);
}});
</script>""")
        yield "404.html", page("Not found", "<h1>Not found</h1><p>That page is not in the archive. Try the search above.</p>")
        yield CSS_PATH, CSS


def write_index(site_dir):
    # ponytail: Pagefind's Python API costs a flat 0.1 s per record (80 min here); the CLI is parallel
    shutil.rmtree(site_dir / "pagefind", ignore_errors=True)
    subprocess.run([sys.executable, "-m", "pagefind", "--site", str(site_dir)], check=True)


def main(db_path, out, force=False, sample=0):
    out = Path(out)
    manifest_path = out / ".manifest.json"
    old = {} if force or not manifest_path.exists() else json.loads(manifest_path.read_text())
    new, changed = {}, 0
    site = Site(db_path, sample)
    for rel, text in site.pages():
        h = hashlib.sha256(text.encode()).hexdigest()
        new[rel] = h
        path = out / rel
        if old.get(rel) != h or not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
            changed += 1
    # Uploaded images (from `just fetch-media`), hard-linked in. UUID names never change, so size is the hash.
    media = Path(db_path).parent / "raw" / "media"
    linked = 0
    for f in media.rglob("*") if media.exists() else ():
        if f.is_file():
            rel = str(f.relative_to(media.parent))
            new[rel] = str(f.stat().st_size)
            if not (out / rel).exists():
                (out / rel).parent.mkdir(parents=True, exist_ok=True)
                os.link(f, out / rel)
                linked += 1
    removed = old.keys() - new.keys()
    for rel in removed:
        (out / rel).unlink(missing_ok=True)
    print(f"{len(site.roots)} threads: {changed} files written, {linked} media linked, {len(removed)} removed")
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
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("db"); ap.add_argument("out")
    ap.add_argument("--force", action="store_true"); ap.add_argument("--sample", type=int, default=0)
    a = ap.parse_args()
    main(a.db, a.out, a.force, a.sample)
