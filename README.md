# bioc-support-archive

A static, read-only archive of support.bioconductor.org. The Postgres backups are rendered to
HTML plus a Pagefind search index, and served by a single Cloudflare Worker from R2.
Decisions are recorded in [docs/adr](docs/adr).

```
pipeline/export.py   pg (throwaway container) -> data/bioc-support-full.duckdb + data/bioc-support-public.sqlite
pipeline/build.py    public.sqlite -> data/build/ (pages, redirects.json, pagefind/, BUILD_ID), incremental
worker/              Hono Worker serving R2 (+ scripts/sync-local.mjs to fill wrangler's local R2)
data -> /data/davsean/bioc-support-archive   (gitignored; raw dumps, exports, build, local R2 state)
```

## Usage

```
just all          # fetch newest dump, export, build, load local R2
just dev          # wrangler dev on the tailnet IP, port 8787
just smoke        # routing checks against the dev server
just publish      # rclone sync to r2:bioc-support-archive + wrangler deploy (needs Cloudflare auth)
```

Needs: docker, uv, node, just, rclone (`r2:` remote).
