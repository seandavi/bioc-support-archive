# 6. Site search with Pagefind

Date: 2026-10-22 · Status: accepted (to be checked against the measured index size)

## Decision
Pagefind's Python API indexes one record per thread (title, question, answers, comments)
straight from SQLite. Filters: type, year, and tags used by at least 50 threads. The index is
static files in R2, and the browser fetches only the chunks it needs. No search server.

## Alternatives
D1 with FTS5 (better phrase and code search, but a database again, and the text is over the
free-tier size). A `site:` hand-off to Google (no work, but depends on Google's index).
