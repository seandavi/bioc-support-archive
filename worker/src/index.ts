// Serves the static archive from R2. Same code path in `wrangler dev` (local R2) and production.
//
// Caching: every response is kept in the edge cache for a year, keyed by BUILD_ID, so deploying
// a new BUILD_ID busts everything at once. Browsers cache fingerprinted files forever and
// revalidate everything else (HTML) after 5 minutes via ETag.
import { Hono, type Context } from "hono";

type Env = { Bindings: { ARCHIVE: R2Bucket; BUILD_ID: string } };
type C = Context<Env>;

const CONTENT_TYPES: Record<string, string> = {
  html: "text/html; charset=utf-8",
  css: "text/css; charset=utf-8",
  js: "text/javascript; charset=utf-8",
  json: "application/json",
  wasm: "application/wasm",
};
const FINGERPRINTED = /[._][0-9a-f]{7,}\.(css|pf_\w+)$/; // style.<hash>.css, pagefind chunks
const EDGE_TTL = "public, max-age=31536000";
const browserTtl = (path: string) =>
  FINGERPRINTED.test(path) ? "public, max-age=31536000, immutable" : "public, max-age=300";

async function serve(c: C, key: string, status = 200): Promise<Response | null> {
  const obj = await c.env.ARCHIVE.get(key, { onlyIf: c.req.raw.headers });
  if (!obj) return null;
  const headers = new Headers({
    "content-type": CONTENT_TYPES[key.split(".").pop() ?? ""] ?? "application/octet-stream",
    etag: obj.httpEtag,
  });
  if (!("body" in obj)) return new Response(null, { status: 304, headers });
  return new Response(obj.body, { status, headers });
}

const notFound = async (c: C) => (await serve(c, "404.html", 404)) ?? c.text("Not found", 404);

// uid -> root uid for answers/comments, loaded once per isolate (~3 MB JSON).
let redirects: Promise<Record<string, string>> | undefined;
const loadRedirects = (c: C) =>
  (redirects ??= c.env.ARCHIVE.get("redirects.json")
    .then((o) => (o ? o.json<Record<string, string>>() : {}))
    .catch((err) => { redirects = undefined; throw err; }));

const app = new Hono<Env>();

app.use("*", async (c, next) => {
  const url = new URL(c.req.url);
  // Query strings are client-side only (search ?q=), so they're not part of the key.
  const key = new Request(`${url.origin}${url.pathname}?build=${c.env.BUILD_ID}`);
  const ttl = browserTtl(url.pathname);
  const hit = await caches.default.match(key);
  if (hit) {
    const fresh = c.req.header("if-none-match") === hit.headers.get("etag");
    c.res = new Response(fresh ? null : hit.body, fresh ? { status: 304, headers: hit.headers } : hit);
    c.res.headers.set("cache-control", ttl);
    return;
  }
  await next();
  if ([200, 301, 404].includes(c.res.status)) {
    const stored = new Response(c.res.clone().body, c.res);
    stored.headers.set("cache-control", EDGE_TTL);
    c.executionCtx.waitUntil(caches.default.put(key, stored));
  }
  c.res.headers.set("cache-control", ttl);
});

app.get("/p/:uid{[0-9]+}", (c) => c.redirect(`/p/${c.req.param("uid")}/`, 301));

app.get("/p/:uid{[0-9]+}/", async (c) => {
  const uid = c.req.param("uid");
  const page = await serve(c, `p/${uid}/index.html`);
  if (page) return page;
  const root = (await loadRedirects(c))[uid];
  return root ? c.redirect(`/p/${root}/#${uid}`, 301) : notFound(c);
});

app.get("*", async (c) => {
  let key = decodeURIComponent(new URL(c.req.url).pathname).slice(1);
  if (key === "" || key.endsWith("/")) key += "index.html";
  return (await serve(c, key)) ?? notFound(c);
});

export default app;
