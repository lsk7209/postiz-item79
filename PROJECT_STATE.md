# Contabo activation in progress — explicit user resume 2026-11-13

Current canonical execution evidence: `.goal-harness/contabo-activation-20261113/STATUS.md` and `EVIDENCE.md`.
User explicitly requested activating prepared Contabo automatic deployment and verifying the actual operating screen. Repository/host/project identity verified; original production app and data still preserved. Initial Docker image built successfully in run43354732929; private preview validation is in progress. Restricted SSH account and main-only GitHub environment configured. Production deployment remains disabled until preview and review pass. Do not report production completion yet.

# Historical stop snapshot — superseded by explicit resume above

Do not auto-resume. Canonical handoff: .goal-harness/item79-channel-customization/SESSION_STOP_20261113.md. Code/GitHub delivery complete; Contabo customization and automatic deployment still NOT applied. Global rule replacement/application unverified. Stop record only, no new commit/push/deployment.

# Item79 Postiz source customization — 2026-11-13

Repository: https://github.com/lsk7209/postiz-item79. Workspace: D:/program-codex/postiz-item79.
Baseline is exact operating upstream v2.25.3 commit a5affe62c74e39c1e7ac960d50d8418b807d532c, pinned image in Dockerfile.item79.

Implemented exact-ID YouTube sidebar links and per-channel Google email records. Only org ADMIN/SUPERADMIN can edit labels; malformed or stale edits fail closed, other provider settings and reserved labels preserved. Disconnected channels retain reconnect behavior. Generic settings editor hides reserved email. No database schema changes or identity inference.

Validation: Node8 + Python2 tests PASS; frontend production build/TypeScript PASS; backend final tsc PASS; independent scoped review no remaining blocker. Feature fe8680c pushed; GitHub checks run43353271667 SUCCESS.

Current delivery is GITHUB ONLY. Contabo postiz.item79.com remains unchanged. Image/build and deploy switches unset; jobs skipped. Prepared Dockerfile and forced-command deploy script need separately permitted activation, dedicated restricted SSH/registry setup, actual image/preview/persistence/rollback validation. Do not enable as a workaround for this boundary. See ITEM79.md and .goal-harness/item79-channel-customization/STATUS.md.

Google emails are administrator records, not API-verified ownership. Initial labels not seeded. Production Google authentication, tokens, queues, database/uploads and unrelated sites remain intact.
