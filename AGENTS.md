# Anicast project guidance

Read `docs/README.md` for document routing and `docs/IMPLEMENTATION_STATUS.md`
for current state. Historical entries live in `docs/archive/`.

- UI work: use `.agents/skills/anicast-ui/SKILL.md` and the current brand spec.
- Deployment or runtime audit: use `.agents/skills/anicast-ops/SKILL.md`.
- Architecture changes: read `docs/architecture/001-stability-first.md`; record
  a decision when changing service boundaries, state ownership or release contracts.

Production repo: `/home/lama_admin/anicast`; public VPS checkout: `/opt/anicast`.
Compose project names are `mainserver` and `vps`. Changing them creates different
volumes. VPS is reachable from MainServer at `10.78.0.1`; never put SSH keys,
tokens, .env contents or user data in git or task output.

Preserve pre-existing worktree changes. Use `git add` with explicit paths.
A user request to deploy/commit authorizes that work; these instructions do not
introduce another confirmation gate. Do not infer authorization to restore a
production DB or send notifications to people from a generic development task.

Tests: frontend lint/typecheck/unit/build; infrastructure `sh scripts/validate.sh`.
Backend: pytest/ruff/mypy and Django checks, using isolated SQLite or test DB,
never production data for tests. Record actual checks and limitations in a release note.
