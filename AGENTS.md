# Anicast project guidance

Start with [docs/README.md](docs/README.md) and the current state in
[IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md). Historical releases,
audits and plans under `docs/archive/` are evidence, not current instructions.

Read only the skill relevant to the task:
- UI: [.agents/skills/anicast-ui/SKILL.md](.agents/skills/anicast-ui/SKILL.md).
- Django/API/data/tasks: [.agents/skills/anicast-backend/SKILL.md](.agents/skills/anicast-backend/SKILL.md).
- Runtime, release, backup, resources: [.agents/skills/anicast-ops/SKILL.md](.agents/skills/anicast-ops/SKILL.md).

For service/state/release-boundary changes read [architecture](docs/architecture/README.md)
and record an ADR when the contract changes. Keep current behavior, decisions and
dated verification in their respective documents; do not append a task diary to status.
Use repository-root paths in prose, relative Markdown links for document navigation.
When moving a document, update callers and links, including archived evidence.

Production checkout: `/home/lama_admin/anicast`; VPS: `/opt/anicast` (no git).
Compose names `mainserver` and `vps` own existing volumes. VPS is reachable from
MainServer at `10.78.0.1`. Never print/commit secrets, tokens, private env or user data.
Preserve existing worktree changes; stage explicit paths. User authorization remains
valid throughout the task; these documents add no blanket plan-approval gate.
Generic implementation/deployment does not authorize restoring production data or
sending test messages to people.

Use the actual check commands in [deployment](docs/operations/DEPLOYMENT.md#validation)
for the changed layer. Documentation/skill-only edits need path/link/frontmatter
validation and diff review, not application builds. Backend tests use isolated
SQLite/test DB; integration drills use disposable resources. Report unrun checks.
