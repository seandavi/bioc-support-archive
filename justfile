backups := "/data/davsean/tmp/bioc-support-site-backups"
build := "data/build"
state := "data/wrangler-state"  # local R2 contents for wrangler dev
sample_build := "data/build-sample"
sample_state := "data/wrangler-state-sample"
host := `tailscale ip -4 2>/dev/null || echo 127.0.0.1`

default:
    @just --list

# Copy the newest nightly dump into data/raw (kept whole, never filtered)
fetch:
    cp -pv "$(ls -1 {{backups}}/bio-database-daily-*.gz | tail -1)" data/raw/

# Restore a dump (default: newest in data/raw) into a throwaway Postgres; export DuckDB + public SQLite
export dump="":
    #!/usr/bin/env bash
    set -euo pipefail
    dump="{{dump}}"; dump="${dump:-$(ls -1 data/raw/bio-database-daily-*.gz | tail -1)}"
    echo "restoring $dump"
    docker run -d --rm --name bioc-restore -e POSTGRES_PASSWORD=restore -p 127.0.0.1:55432:5432 postgres:17 >/dev/null
    trap 'docker stop bioc-restore >/dev/null' EXIT
    until docker exec bioc-restore psql -U postgres -qc 'select 1' >/dev/null 2>&1; do sleep 1; done
    zcat "$dump" | docker exec -i bioc-restore psql -U postgres -q -v ON_ERROR_STOP=1 >/dev/null
    rm -f data/bioc-support-full.duckdb data/bioc-support-public.sqlite
    uv run pipeline/export.py data/bioc-support-full.duckdb data/bioc-support-public.sqlite

# Render pages + search index (incremental; pass --force to rebuild everything)
build *flags:
    uv run pipeline/build.py data/bioc-support-public.sqlite {{build}} {{flags}}

test:
    uv run pytest -q pipeline

# Mirror a build into wrangler's local R2 (incremental). Stops `just dev`: both lock the store.
sync-local b=build s=state:
    -pkill -f 'node_modules/.bin/[w]rangler dev' && sleep 2
    cd worker && node scripts/sync-local.mjs ../{{b}} ../{{s}}

# Serve the Worker locally on the tailnet address
dev b=build s=state port="8787":
    cd worker && npx wrangler dev --ip {{host}} --port {{port}} --persist-to ../{{s}} --var BUILD_ID:$(cat ../{{b}}/BUILD_ID)

# Small build (N most-voted + N most-recent threads) for design iteration: build, load, serve
sample n="200":
    uv run pipeline/build.py data/bioc-support-public.sqlite {{sample_build}} --sample {{n}}
    just sync-local {{sample_build}} {{sample_state}}
    just dev {{sample_build}} {{sample_state}}

# Check routing against a running dev server (test URLs are taken from the build)
smoke b=build port="8787":
    #!/usr/bin/env bash
    set -euo pipefail
    base=http://{{host}}:{{port}}
    read -r child root < <(python3 -c 'import json,sys; k,v=next(iter(json.load(open(sys.argv[1])).items())); print(k,v)' {{b}}/redirects.json)
    check() { got=$(curl -s -o /dev/null -w '%{http_code} %{redirect_url}' "$base$1"); echo "$1 -> $got"; [[ "$got" == $2* ]]; }
    check / 200
    check /p/$root/ 200
    check /p/$child/ "301 $base/p/$root/#$child"
    check /p/$root "301 $base/p/$root/"
    check /search/ 200
    check /pagefind/pagefind-component-ui.js 200
    check /nope 404
    echo ok

# Upload the build to the real R2 bucket, then deploy the Worker with the new BUILD_ID
publish b=build bucket="bioc-support-archive":
    rclone mkdir r2:{{bucket}}
    rclone sync --checksum --exclude .manifest.json --transfers 64 --checkers 64 --fast-list {{b}} r2:{{bucket}}
    cd worker && npx wrangler deploy --var BUILD_ID:$(cat ../{{b}}/BUILD_ID)

# Full pipeline from the newest backup
all: fetch export build sync-local
