# 3. What goes into the public data

Date: 2026-10-22 · Status: accepted

## Decision
The public SQLite file, and everything built from it, contains only:
- `post`: posts that are not spam (`spam != 0`), not deleted (`status != 4`), not written by an
  account marked as a spammer (`profile.state != 4`), not inside a removed thread, and not under a
  removed parent. Closed and off-topic posts stay, because they were publicly visible.
- `user`: id, uid, display name, handle, role, score and join date, only for people who wrote
  or edited a kept post.
- `post_tag`.

Emails, password hashes, sessions, OAuth tokens, private messages, per-person votes and
subscriptions, and profile bio/website/location are left out.

Codes come from biostar-central `forum/models.py` and `accounts/models.py`. Note that
`spam=0` means SPAM, and `status=3` means CLOSED, not deleted.

## Consequences
Profile pages (`/u/<uid>/`, issue #4) are built from these fields only. Score/reputation,
role, bio, location and last-seen are not shown.
