# 1. Static archive served by one Worker from R2

Date: 2026-10-22 · Status: accepted

## Context
support.bioconductor.org (Biostar, Django + Postgres 12) is being decommissioned. Its content
must stay readable at the same URLs, with as little infrastructure as possible. The data
will never change again, except when we redo the export from a later dump.

## Decision
Pre-render every thread to static HTML at build time and store the files in an R2 bucket.
One Cloudflare Worker (Hono) maps URLs to R2 keys, adds the answer/comment redirects, and
handles caching. There is no database at runtime.

## Consequences
- Nothing to patch or migrate, and no injection surface. Cost is R2 storage plus Worker requests.
- R2 has no file-count limit (Static Assets and Pages do; a full build is ~100k files).
- Any change to the content means a rebuild and re-upload (both incremental, see ADR 5).
- Hono keeps the Worker portable to Node/Bun if Cloudflare is ever dropped.
