// Mirror a build directory into wrangler's local R2 (what `wrangler dev --persist-to` reads).
// Incremental: <persist_dir>/synced.json records the MD5 of each key last pushed; only changed
// files are uploaded (wrangler r2 bulk put) and keys no longer in the build are deleted.
// usage: node scripts/sync-local.mjs <build_dir> <persist_dir>
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync } from "node:fs";
import { mkdir, readdir, readFile, writeFile } from "node:fs/promises";
import { join, relative, resolve } from "node:path";

const BUCKET = "bioc-support-archive"; // must match bucket_name in wrangler.jsonc
const [dir, persistTo] = process.argv.slice(2).map((p) => resolve(p));
const syncedPath = join(persistTo, "synced.json");
const synced = existsSync(syncedPath) ? JSON.parse(await readFile(syncedPath, "utf8")) : {};
const wrangler = (...args) =>
  execFileSync("npx", ["wrangler", "r2", ...args, "--local", "--persist-to", persistTo], { stdio: "inherit" });

const files = (await readdir(dir, { recursive: true, withFileTypes: true }))
  .filter((d) => d.isFile() && d.name !== ".manifest.json")
  .map((d) => join(d.parentPath, d.name));

const now = {}, changed = [];
for (const f of files) {
  const key = relative(dir, f);
  now[key] = createHash("md5").update(await readFile(f)).digest("hex");
  if (synced[key] !== now[key]) changed.push({ key, file: f });
}
const stale = Object.keys(synced).filter((k) => !(k in now));

await mkdir(persistTo, { recursive: true });
if (changed.length) {
  const list = join(persistTo, "bulk-put.json");
  await writeFile(list, JSON.stringify(changed));
  wrangler("bulk", "put", BUCKET, "--filename", list, "--concurrency", "64");
}
for (const key of stale) wrangler("object", "delete", `${BUCKET}/${key}`); // ponytail: one call per key; fine for a handful
await writeFile(syncedPath, JSON.stringify(now));
console.log(`${files.length} files: ${changed.length} uploaded, ${stale.length} deleted`);
