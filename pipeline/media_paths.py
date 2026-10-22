"""Print every /media/images/... path referenced by any post (all posts, not just public ones).

usage: media_paths.py <full.duckdb>
"""

import re
import sys

import duckdb

PAT = re.compile(r"""(?:https?://(?:www\.)?support\.bioconductor\.org)?(/media/images/[\w\-./]+)""", re.I)

con = duckdb.connect(sys.argv[1], read_only=True)
paths = set()
for h, c in con.execute("SELECT html, content FROM forum_post WHERE html LIKE '%/media/images/%' OR content LIKE '%/media/images/%'").fetchall():
    for s in (h, c):
        paths.update(m.group(1).rstrip(".") for m in PAT.finditer(s))
print("\n".join(sorted(paths)))
