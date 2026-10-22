"""Generate docs/figures/data-flow.svg (stdlib only). Run: python3 docs/figures/data_flow.py"""

from html import escape
from pathlib import Path

KINDS = {  # kind: (fill, stroke, legend label)
    "source": ("#fdf3e1", "#c98a1b", "External source"),
    "process": ("#eef2f6", "#5f6b76", "Pipeline step (just recipe)"),
    "private": ("#fbe9e9", "#b54747", "Private data (never published)"),
    "public": ("#e8f2fa", "#1a81c2", "Publishable data"),
    "cloud": ("#eef6e6", "#5f8f22", "Cloudflare runtime"),
}
W, BW, BH = 1160, 220, 74
C = [20, 320, 620, 920]  # column x positions
BOXES = {  # name: (x, y, kind, lines)
    "dump": (C[0], 90, "source", ["Nightly pg_dump", "bio-database-daily-*.gz", "Postgres 12, plain SQL"]),
    "pg": (C[1], 90, "process", ["Postgres 17 container", "throwaway, via docker", "just export"]),
    "full": (C[2], 20, "private", ["bioc-support-full.duckdb", "all 51 tables, archival copy"]),
    "public": (C[2], 150, "public", ["bioc-support-public.sqlite", "post · user · post_tag", "spam and deleted removed"]),
    "build": (C[3], 150, "process", ["build.py + Pagefind CLI", "content-hash manifest", "just build"]),
    "live": (C[0], 290, "source", ["Live site", "support.bioconductor.org", "/media/images/*"]),
    "fetch": (C[1], 290, "process", ["Download images", "paths from full.duckdb", "just fetch-media"]),
    "media": (C[2], 290, "public", ["data/raw/media/", "2,189 images"]),
    "local": (C[2], 420, "process", ["Local R2 + wrangler dev", "same Worker code", "just sync-local / dev"]),
    "out": (C[3], 420, "public", ["data/build/", "pages · redirects · media", "search index · BUILD_ID"]),
    "browser": (C[1], 550, "source", ["Browser", "static pages", "client-side search"]),
    "worker": (C[2], 550, "cloud", ["Hono Worker", "redirects · edge cache", "keyed by BUILD_ID"]),
    "r2": (C[3], 550, "cloud", ["R2 bucket", "bioc-support-archive", "just publish (rclone)"]),
}
EDGES = [  # (from, from_side, to, to_side, label, dashed)
    ("dump", "r", "pg", "l", "restore", False),
    ("pg", "r", "full", "l", "", False),
    ("pg", "r", "public", "l", "", False),
    ("public", "r", "build", "l", "render", False),
    ("live", "r", "fetch", "l", "HTTP", False),
    ("fetch", "r", "media", "l", "", False),
    ("media", "r", "build", "bl", "hard-link", False),
    ("build", "br", "out", "tr", "", False),
    ("out", "l", "local", "r", "test", True),
    ("out", "b", "r2", "t", "rclone sync", False),
    ("r2", "l", "worker", "r", "read", False),
    ("worker", "l", "browser", "r", "serve", False),
]


def anchor(name, side):
    x, y, *_ = BOXES[name]
    fx = {"l": 0, "r": 1, "t": .5, "b": .5, "tl": .3, "bl": .3, "tr": .7, "br": .7}[side]
    fy = .5 if side in "lr" else (0 if side.startswith("t") else 1)
    return x + BW * fx, y + BH * fy


def svg():
    legend_y = 670
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {legend_y + 60}" font-family="system-ui, -apple-system, Segoe UI, Roboto, sans-serif">',
           '<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
           '<path d="M0 0L10 5L0 10z" fill="#5f6b76"/></marker></defs>',
           f'<rect width="{W}" height="{legend_y + 60}" fill="#fff"/>']
    labels = []
    for a, sa, b, sb, label, dashed in EDGES:
        (x1, y1), (x2, y2) = anchor(a, sa), anchor(b, sb)
        sa, sb = sa[0], sb[0]
        # elbow path: leave horizontally from l/r anchors, vertically from t/b
        mid = f"L{x2} {y1}" if sa in "lr" and sb in "tb" else f"L{x1} {y2}" if sa in "tb" and sb in "lr" else \
              f"L{(x1 + x2) / 2} {y1} L{(x1 + x2) / 2} {y2}" if sa in "lr" else f"L{x1} {(y1 + y2) / 2} L{x2} {(y1 + y2) / 2}"
        dash = ' stroke-dasharray="5 4"' if dashed else ""
        out.append(f'<path d="M{x1} {y1} {mid} L{x2} {y2}" fill="none" stroke="#5f6b76" stroke-width="1.6"{dash} marker-end="url(#a)"/>')
        if label:
            if sa in "lr" and sb in "lr":
                lx, ly, anc = (x1 + x2) / 2, min(y1, y2) - 6, "middle"
            elif sa in "lr":
                lx, ly, anc = (x1 + x2) / 2, y1 - 6, "middle"
            else:
                fits = x1 + 6 + 7 * len(label) < W  # put vertical labels on whichever side has room
                lx, ly, anc = (x1 + 6, (y1 + y2) / 2 + 4, "start") if fits else (x1 - 6, (y1 + y2) / 2 + 4, "end")
            labels.append(f'<text x="{lx}" y="{ly}" font-size="12" fill="#5f6b76" text-anchor="{anc}" '
                          f'stroke="#fff" stroke-width="4" paint-order="stroke">{escape(label)}</text>')
    for x, y, kind, lines in BOXES.values():
        fill, stroke, _ = KINDS[kind]
        out.append(f'<rect x="{x}" y="{y}" width="{BW}" height="{BH}" rx="8" fill="{fill}" stroke="{stroke}" stroke-width="1.6"/>')
        y0 = y + BH / 2 - (len(lines) - 1) * 9 + 4
        for i, t in enumerate(lines):
            weight, size, color = ("600", 14, "#1f2933") if i == 0 else ("400", 12, "#3d4852")
            out.append(f'<text x="{x + BW / 2}" y="{y0 + i * 18}" text-anchor="middle" font-size="{size}" font-weight="{weight}" fill="{color}">{escape(t)}</text>')
    out += labels
    out.append(f'<text x="20" y="{legend_y}" font-size="13" font-weight="600" fill="#1f2933">Legend</text>')
    x = 20
    for fill, stroke, label in KINDS.values():
        out.append(f'<rect x="{x}" y="{legend_y + 14}" width="18" height="14" rx="3" fill="{fill}" stroke="{stroke}" stroke-width="1.4"/>')
        out.append(f'<text x="{x + 24}" y="{legend_y + 26}" font-size="12" fill="#3d4852">{escape(label)}</text>')
        x += 32 + len(label) * 6.6
    out.append(f'<path d="M{x} {legend_y + 21} h28" stroke="#5f6b76" stroke-width="1.6" marker-end="url(#a)"/>'
               f'<text x="{x + 34}" y="{legend_y + 26}" font-size="12" fill="#3d4852">data flow</text>')
    x += 110
    out.append(f'<path d="M{x} {legend_y + 21} h28" stroke="#5f6b76" stroke-width="1.6" stroke-dasharray="5 4" marker-end="url(#a)"/>'
               f'<text x="{x + 34}" y="{legend_y + 26}" font-size="12" fill="#3d4852">local testing only</text>')
    out.append("</svg>")
    return "\n".join(out)


if __name__ == "__main__":
    Path(__file__).with_name("data-flow.svg").write_text(svg())
