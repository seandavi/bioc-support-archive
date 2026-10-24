# AGENTS.md

Conventions for anyone (human or agent) changing this repo. The design record is
[README.md](README.md) plus the ADRs in [docs/adr](docs/adr); read the ADRs that touch your change
before changing it.

## What this is

A static, read-only archive of support.bioconductor.org: a Python pipeline renders every thread to
HTML from a nightly Postgres dump, and a small Hono Worker serves the files from R2. No runtime
database, no application server (ADR 1).

## Stack (decided; do not substitute)

- Python ≥ 3.11 with **uv** (`uv sync`, `uv run`); DuckDB for the export; **polars** if a dataframe
  is ever needed (not pandas). Lint/format: `uvx ruff check`, `uvx ruff format`.
- **Pagefind** CLI for search (ADR 6). Not the Python API, not a search server.
- Worker: TypeScript, **Hono**, Wrangler, R2 binding `ARCHIVE`. Match the surrounding code.
- `just` is the task runner. Figures are stdlib Python scripts in `docs/figures/` (`just figures`);
  never hand-edit the SVG.

## Layout

```
pipeline/export.py       dump (restored Postgres) → private DuckDB + public SQLite  (ADR 2, 3)
pipeline/media_paths.py  image paths referenced by posts
pipeline/build.py        public SQLite → HTML pages, redirects.json, Pagefind index (ADR 4, 5, 6)
pipeline/test_build.py   tests
worker/src/index.ts      URL → R2 key, answer/comment redirects, edge caching (ADR 1, 4, 5)
docs/adr/                decisions;  docs/figures/  generated figures
data/                    dumps, exports, builds, images — gitignored, never committed
```

## Rules

- **Privacy first (ADR 3).** Only the public subset may reach the public SQLite file, the build, R2,
  logs, fixtures or commits. Any change to the filters in `pipeline/export.py` updates ADR 3 and gets
  privacy review. Remember: `spam=0` means SPAM, `status=3` is CLOSED (not deleted), `status=4` is
  deleted.
- **Keep old URLs working (ADR 4).** Threads at `/p/<uid>/`; answer/comment uids 301 to
  `/p/<root>/#<uid>`; generated links are root-relative. URL changes update ADR 4.
- **Incremental and idempotent builds (ADR 5).** Unchanged pages are not rewritten; `BUILD_ID` is
  the manifest hash.
- **Tests never use the real data.** The dump is private and not distributed: tests build small
  synthetic SQLite/DuckDB fixtures in code, and never read `data/`. No network in tests.
- Rendering must escape or sanitize post HTML; 25 years of user content is untrusted input.
- Raw sources are landed whole (the full DuckDB keeps every table); filtering happens only on the way
  to the public file.
- No secrets in code, fixtures or logs. R2 and Cloudflare credentials come from the environment
  (rclone/wrangler config); GCP Secret Manager `cdsci-infra` is the source of truth.

## Commands

- `uv sync` and `(cd worker && npm install)`: install.
- `just test`: Python tests (`uv run pytest -q pipeline`).
- `uvx ruff check pipeline && uvx ruff format --check pipeline`: lint.
- `cd worker && npx wrangler deploy --dry-run --outdir /tmp/bsa-dist`: bundle/typecheck the Worker
  without deploying.
- `just sample` / `just dev` / `just smoke`: local build, serve and route check (needs a public-subset
  SQLite file in `data/`; not available in a fresh checkout).
- `just publish` deploys to production. **Agents never run it.**

## Git

- Branch per issue: `issue-<n>-<slug>`, in a worktree under `../bioc-support-archive-worktrees/`.
  PRs say `Closes #<n>`. One change per PR; describe what you checked.
- Small, well-described commits; code commits carry a `Co-Authored-By` trailer when an agent wrote
  them. Never `git stash`. Never force-push `main`. Never commit `data/`.
- Issues and PRs waiting on a person carry the `needs:human` label. The factory workflow is in
  [.pi/factory.md](.pi/factory.md).
