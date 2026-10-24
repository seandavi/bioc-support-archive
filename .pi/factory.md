# The factory

Issues here run through the shared [pi-factory](https://github.com/seandavi/pi-factory) engine:
spec (Opus) → implement (Sonnet) → parallel review lenses (Opus) → up to two revise rounds → PR,
which a person merges. How it works and every config field: its
[docs/factory.md](https://github.com/seandavi/pi-factory/blob/main/docs/factory.md).

- **Config:** [`factory.json`](factory.json): the design record (README + ADRs), lenses (`code`
  always; `ux` and `privacy` by label `review:ux` / `review:privacy`), project rules for the
  stages, and checks (`just test`, ruff on `pipeline/`, the Worker dry-run).
  [`../AGENTS.md`](../AGENTS.md) is what every stage reads first.
- **Seams:** label `seam` for the export query, the page templates, the URL scheme and the Worker;
  reviewers then rate inherited defects by blast radius.
- **Install** (once per machine): `pi install git:github.com/seandavi/pi-factory`;
  update with `pi update --extensions`.
- **Run:** in pi on onclappc02, inside this repo: `/factory <issue>` (`--dry-run` to preview,
  `--start-at review` to re-review a branch). The queue: `gh issue list -l needs:human` and
  `gh pr list -l needs:human`. Label `no-factory` marks issues to do by hand.
