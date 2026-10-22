# The factory: spec → implement → review → revise → PR

Ported from [seandavi/bioc-mcp](https://github.com/seandavi/bioc-mcp/blob/main/.pi/factory.md),
where it ran its first dozen issues. An experiment in running issues through a fixed loop of
[pi-subagents](https://github.com/nicobailon/pi-subagents), with the strong model where judgment
matters and the fast model where volume does. The script is
[`.pi/workflows/factory.js`](workflows/factory.js).

| Stage | Model | Agent | Writes | Output |
|---|---|---|---|---|
| Spec | Opus | `worker` | `docs/specs/<issue>-<slug>.md`, one commit | `{status, spec_path, blocking_questions}` |
| Implement | Sonnet | `worker` | code + tests, small commits | `{status, summary, changed_files, checks}` |
| Review | Opus | `reviewer` (read-only), one per lens, in parallel | nothing | `{verdict, findings[]}` |
| Revise | Sonnet | `worker` | fixes for blocker/major findings, spec updates | `{status, responses[], checks}` |
| PR | Sonnet | `worker` | push, follow-up issue, `gh pr create` (or edit) | `{pr_url, draft, followup_issue}` |
| Flag | Haiku | `worker` | `needs:human` label + comment on the issue | — |

**Review lenses** (chosen per issue from labels):

- `code` (always): correctness against the spec, tests on synthetic fixtures (never the private
  dump), incremental/idempotent builds (ADR 5), a thin Worker (ADR 1), spec and code in agreement.
- `ux` (label `review:ux`): the reader landing on an old link: URLs and anchors still resolve
  (ADR 4), mobile, light/dark, accessibility, search quality (ADR 6), rendering of code, images and
  long threads; contributor docs.
- `privacy` (label `review:privacy`): nothing outside the public subset (ADR 3) reaches the public
  file, build, R2, logs or fixtures; HTML escaping; no off-site redirects; no secrets.

**Seams** (label `seam`, arg `seam: true`): for shared foundations that later issues build on, the
reviewers are told to rate inherited defects by blast radius, so a bypassable guard is `major`
even when nothing calls it yet. (Added in bioc-mcp after four such findings came back as `minor`.) Use it here for the export
query, the page templates, the URL scheme and the Worker.

**Finding ids** are `<lens>-r<round>-<n>`, unique across rounds.

**Revise rounds:** at most two. Only `blocker` and `major` findings trigger a round, and only the
lenses that asked for changes review again. Revise fixes root causes and updates the spec when a
fix changes an interface, rule or example. Re-reviewers see the earlier findings and the responses
and judge the fix itself: a symptom patch that leaves the root cause is a new `major`. Added in bioc-mcp
after its #2, where a post-hoc redirect check was accepted in round 1 and later replaced by hand. If
findings remain after round two, the PR opens as a **draft** listing them.

**Follow-ups:** `minor` and `nit` findings are filed as one issue, "Follow-ups from the #n review"
(a sub-issue of `parent` when given), and the PR links it.

**Stops:** a spec with blocking questions stops the run before any code is written; an
implementation reporting `blocked` stops before review. Both label the issue `needs:human` and
comment why. Every PR the factory opens is labelled `needs:human` too; remove the label when you
have acted. Your queue is `gh issue list -l needs:human` plus `gh pr list -l needs:human`.

**Resuming:** `startAt: "implement"` skips the spec stage (the spec must already be on the branch);
`startAt: "review"` re-reviews an existing branch, e.g. after hand edits, and replaces the body of
its PR if one exists. Use it instead of fixing review findings by hand outside the factory, so the
record stays in the PR.

**Never automated:** merging. A human merges, from the main session.

## Running it

Prepare an isolated worktree for the issue (the workflow sandbox has no shell), then launch:

Run it from a pi session on onclappc02 (pi-subagents and the `claude-bridge` models are
installed there):

```sh
cd ~/Documents/git/bioc-support-archive && git fetch origin
git worktree add -b issue-1-dark-on-dark ../bioc-support-archive-worktrees/issue-1 origin/main
```

```js
subagent({
  workflow: "./.pi/workflows/factory.js",
  cwd: "~/Documents/git/bioc-support-archive",
  async: true,             // claude-bridge children must run async
  args: {
    repo: "seandavi/bioc-support-archive", issue: 1, slug: "dark-on-dark",
    worktree: "/home/davsean/Documents/git/bioc-support-archive-worktrees/issue-1",
    branch: "issue-1-dark-on-dark", lenses: ["code", "ux"],   // add "privacy" for data/export/Worker changes
    // seam: true,          // export query, templates, URL scheme, Worker
    // parent: <n>,         // tracking issue for the follow-up issue
    // startAt: "review"    // re-review an existing branch
  }
})
```

Do not `/reload` pi while a run is going: it stops the workflow script (children keep running).
Relaunch with the same args plus `options: { reuseFrom: "<run id>" }` to resume.

## What to watch while it is an experiment

- Do the reviews find real problems, or restate the spec? (Count findings that led to a change.)
- Does round two ever happen, and does it converge?
- Time and tokens per stage, from the run receipts.
- Severity calibration: how many `minor` findings had to be fixed before merge anyway? (bioc-mcp #2:
  five, all in a shared seam; the `seam` note and fix-judging are the response.)
- Work done outside the factory after a run. Each instance is a gap in the loop; prefer
  `startAt: "review"`.
- Skills: none are wired in yet (`BUILD_SKILLS`/`LENS_SKILLS` in the script). bioc-mcp is
  trialling `workers-best-practices`; adopt it here if that trial pays off.
- No CI yet: the checks are what the stages run locally. Adding CI is a good first factory issue.
