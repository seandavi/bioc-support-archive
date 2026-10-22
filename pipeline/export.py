"""Export the restored Biostar Postgres DB to a full DuckDB archive and a public SQLite subset.

Codes (biostar-central forum/models.py, accounts/models.py):
  post.status: 0 pending, 1 open, 2 off-topic, 3 closed, 4 deleted
  post.spam:   0 SPAM, 1 not spam, 2 default
  profile.state: 0 new, 1 trusted, 2 suspended, 3 banned, 4 spammer
"""

import sys

import duckdb

PG = "postgresql://postgres:restore@127.0.0.1:55432/postgres"
full_path, public_path = sys.argv[1], sys.argv[2]

con = duckdb.connect(full_path)
con.execute("SET TimeZone = 'UTC'")
con.execute("INSTALL postgres; LOAD postgres; INSTALL sqlite; LOAD sqlite;")
con.execute(f"ATTACH '{PG}' AS pg (TYPE postgres, READ_ONLY)")

# Full private archive: every table, as-is.
tables = [r[0] for r in con.execute(
    "SELECT table_name FROM pg.information_schema.tables "
    "WHERE table_schema = 'public' AND table_type = 'BASE TABLE' ORDER BY 1").fetchall()]
for t in tables:
    con.execute(f'CREATE OR REPLACE TABLE "{t}" AS SELECT * FROM pg.public."{t}"')
con.execute("DETACH pg")

# Public subset: no emails, passwords, sessions, tokens, messages, votes-by-user.
con.execute(f"ATTACH '{public_path}' AS pub (TYPE sqlite)")
con.execute("""
CREATE TEMP TABLE keep AS
SELECT f.id
FROM forum_post f
JOIN forum_post r ON r.id = f.root_id
JOIN accounts_profile a ON a.user_id = f.author_id
JOIN accounts_profile ra ON ra.user_id = r.author_id
WHERE f.status <> 4 AND f.spam <> 0 AND a.state <> 4
  AND r.status <> 4 AND r.spam <> 0 AND ra.state <> 4
""")
# Drop replies whose parent was removed (e.g. comments under a deleted answer), to a fixed point.
while con.execute("""
    DELETE FROM keep WHERE id IN (
      SELECT f.id FROM forum_post f SEMI JOIN keep k ON k.id = f.id
      WHERE f.parent_id IS NOT NULL AND f.parent_id NOT IN (SELECT id FROM keep))
""").fetchone()[0]:
    pass
con.execute("""
CREATE TABLE pub.post AS
SELECT f.id, f.uid, f.root_id, f.parent_id, f.type, f.status, f.is_toplevel,
       f.title, f.tag_val AS tags, f.author_id, f.lastedit_user_id,
       f.creation_date, f.lastedit_date,
       f.vote_count, f.thread_votecount, f.view_count, f.answer_count,
       f.accept_count, f.reply_count, f.comment_count, f.book_count,
       f.content, f.html
FROM forum_post f SEMI JOIN keep k ON k.id = f.id
ORDER BY f.id
""")
con.execute("""
CREATE TABLE pub."user" AS
SELECT p.user_id AS id, p.uid, p.name, p.handle, p.role, p.score, p.date_joined
FROM accounts_profile p
WHERE p.user_id IN (SELECT author_id FROM pub.post
                    UNION SELECT lastedit_user_id FROM pub.post)
ORDER BY p.user_id
""")
con.execute("""
CREATE TABLE pub.post_tag AS
SELECT ti.object_id AS post_id, t.name AS tag
FROM taggit_taggeditem ti
JOIN taggit_tag t ON t.id = ti.tag_id
JOIN django_content_type ct ON ct.id = ti.content_type_id
WHERE ct.app_label = 'forum' AND ct.model = 'post'
  AND ti.object_id IN (SELECT id FROM pub.post)
ORDER BY 1, 2
""")
for t in ("post", "user", "post_tag"):
    n = con.execute(f'SELECT count(*) FROM pub."{t}"').fetchone()[0]
    print(f"public.{t}: {n}")
print(f"full archive: {len(tables)} tables")
