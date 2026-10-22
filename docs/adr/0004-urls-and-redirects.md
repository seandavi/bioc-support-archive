# 4. Keep the old URLs; all generated links are root-relative

Date: 2026-10-22 · Status: accepted

## Decision
- Thread pages live at `/p/<uid>/`. They use the post `uid`, which is what the live site exposed, not the internal `id`.
- `/p/<answer or comment uid>/` returns a 301 to `/p/<root uid>/#<uid>`, matching the live site's
  redirect (which was a 302). The map is `redirects.json`, loaded once per Worker isolate.
- Absolute links to `support.bioconductor.org` inside post HTML are rewritten to root-relative
  paths at build time. Templates use only root-relative paths, so one build works on
  localhost, the tailnet, workers.dev or the real domain.

## Consequences
- Other old paths (`/t/<tag>/`, `/u/<user>/`) return 404 until they are added.
- Uploaded images are not in the database. `just fetch-media` downloads every `/media/images/` path referenced by
  any post (2,189 files, 248 MB, fetched 2026-10-22 from the live site) into `data/raw/media/`; the build hard-links
  them to the same paths. Files have no extension and are served as `application/octet-stream`, as on the live site.
