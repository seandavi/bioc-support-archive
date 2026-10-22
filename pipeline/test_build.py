from build import rewrite_links


def test_rewrite_links():
    assert rewrite_links('<a href="https://support.bioconductor.org/p/123/">') == '<a href="/p/123/">'
    assert rewrite_links('<a href="http://www.support.bioconductor.org/p/1/#2">') == '<a href="/p/1/#2">'
    assert rewrite_links('see https://support.bioconductor.org now') == 'see  now'
    # other hosts untouched, including look-alikes
    assert rewrite_links('https://www.biostars.org/p/1/') == 'https://www.biostars.org/p/1/'
    assert rewrite_links('https://support.bioconductor.org.evil.com/') == 'https://support.bioconductor.org.evil.com/'
