# 2. Convert the pg_dump via a throwaway Postgres container

Date: 2026-10-22 · Status: accepted

## Context
The nightly backups are plain-SQL `pg_dump` files (Postgres 12). Neither SQLite nor DuckDB can
load them directly: COPY blocks use Postgres text escapes, `\N` nulls and Postgres types.

## Decision
`just export` restores the dump into a disposable `postgres:17` Docker container, copies the
tables into DuckDB with DuckDB's postgres extension, then removes the container. The shared
Postgres cluster is never touched. (Rootless podman fails on onclappc02: there is no subuid range.)

## Consequences
- The escapes and types are handled by real Postgres, not by a hand-written parser.
- Outputs: `bioc-support-full.duckdb` (all 51 tables, private) and
  `bioc-support-public.sqlite` (the publishable subset, ADR 3).
- DuckDB is pinned to a stable 1.4 release, not the 2.0 alpha CLI installed on the host.
