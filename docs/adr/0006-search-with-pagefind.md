# 6. Site search with Pagefind

Date: 2026-10-22 · Status: accepted (to be checked against the measured index size)

## Decision
The Pagefind CLI indexes the rendered thread pages, one record per thread (title, question,
answers, comments), using `data-pagefind-body/filter/meta/ignore` attributes. Filters: type,
year, and tags used by at least 50 threads. A full index of 47,277 threads takes about 70 s.
The Python API was rejected because it costs a flat 0.1 s per record, about 80 minutes here. The index is
static files in R2, and the browser fetches only the chunks it needs. No search server.

## Consequences
At this size the Component UI is the bottleneck, not the index. It renders one element per hit,
and a common term like `limma` has 9,000+ hits. It has no paging, so result lists are capped at
100 (search page) and 50 (header modal). Faceted mode is switched on only after the index loads,
because otherwise Pagefind opens with an unfiltered search over every thread (about 6 s). A cold
tag-only search (`?tag=`) still loads the whole index, so it takes several seconds.

## Alternatives
D1 with FTS5 (better phrase and code search, but a database again, and the text is over the
free-tier size). A `site:` hand-off to Google (no work, but depends on Google's index).
