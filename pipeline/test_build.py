from build import rewrite_links


def test_rewrite_links():
    assert rewrite_links('<a href="https://support.bioconductor.org/p/123/">') == '<a href="/p/123/">'
    assert rewrite_links('<a href="http://www.support.bioconductor.org/p/1/#2">') == '<a href="/p/1/#2">'
    assert rewrite_links('see https://support.bioconductor.org now') == 'see  now'
    # other hosts untouched, including look-alikes
    assert rewrite_links('https://www.biostars.org/p/1/') == 'https://www.biostars.org/p/1/'
    assert rewrite_links('https://support.bioconductor.org.evil.com/') == 'https://support.bioconductor.org.evil.com/'


def test_user_page(tmp_path):
    import sqlite3
    from build import Site
    db = tmp_path / "t.sqlite"
    con = sqlite3.connect(db)
    con.executescript("""
    CREATE TABLE user(id, uid, name, handle, role, score, date_joined);
    CREATE TABLE post(id, uid, root_id, parent_id, type, is_toplevel, title, tags, author_id,
                      creation_date, vote_count, thread_votecount, view_count, answer_count, accept_count, html);
    CREATE TABLE post_tag(post_id, tag);
    INSERT INTO user VALUES (1, '10', 'Asker', '', 0, 0, '2010-01-01'), (2, '20', 'Helper', '', 0, 0, '2011-01-01');
    INSERT INTO post VALUES (1, '100', 1, NULL, 0, 1, 'Q title', '', 1, '2012-01-01', 0, 3, 5, 1, 0, '<p>q</p>'),
                            (2, '101', 1, 1, 1, 0, '', '', 2, '2012-01-02', 3, 0, 0, 0, 1, '<p>a</p>'),
                            (3, '102', 1, 2, 6, 0, '', '', 1, '2012-01-03', 0, 0, 0, 0, 0, '<p>thanks</p>');
    """)
    con.commit()
    pages = dict(Site(db).pages())
    helper = pages["u/20/index.html"]
    assert "<dt>Answers</dt><dd>1</dd>" in helper and "<dt>Accepted answers</dt><dd>1</dd>" in helper
    assert 'href="/p/100/#101"' in helper and "accepted" in helper
    asker = pages["u/10/index.html"]
    assert "<dt>Questions</dt><dd>1</dd>" in asker and "<dt>Comments</dt><dd>1</dd>" in asker
    assert 'href="/u/20/"' in pages["p/100/index.html"]
