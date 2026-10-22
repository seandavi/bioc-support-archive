# 5. Incremental builds and build-keyed caching

Date: 2026-10-22 · Status: accepted

## Context
We expect to redo the export from later dumps. Content is otherwise immutable, so it should be
cached as long as possible, but a new build must show up at once.

## Decision
- `build.py` keeps a manifest of content hashes. It writes only pages that changed, deletes
  pages for threads that are gone, and rebuilds the Pagefind index only when something changed
  (Pagefind itself cannot update an index in place).
- Uploads are incremental by checksum: `rclone sync --checksum` for real R2, and for the local R2 used by `wrangler dev`, a
  record of the MD5 last pushed per key, with changes sent through `wrangler r2 bulk put --local`.
- Each build writes a `BUILD_ID` (a hash of the manifest), and it is deployed as a Worker var.
  The edge cache key includes it and edge entries are kept for a year, so a deploy busts
  everything at once.
- Browsers cache fingerprinted files (`style.<hash>.css`, Pagefind chunks) forever, as
  `immutable`. HTML gets 5 minutes plus an ETag, because browser caches can't be busted.

## Consequences
- Right after a deploy, every request misses the edge cache once and is read from R2. That's cheap.
- The Cache API does nothing on `*.workers.dev`. Edge caching needs the custom domain.
