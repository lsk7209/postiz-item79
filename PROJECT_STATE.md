# Contabo automatic deployment verified — 2026-11-13

Current canonical execution evidence: `.goal-harness/contabo-activation-20261113/STATUS.md` and `EVIDENCE.md`.
DONE. https://postiz.item79.com/launches is running source commit `2c951cf3b67520ad449bb7d5a9d850518dbf3a89`, immutable image `ghcr.io/lsk7209/postiz-item79@sha256:2bad13fd750daa7b6c1a55f83f85955c47869ac46117cb9f0d7eb74407a95900`. Actual main-push workflow43357711188 checks/image/deploy all SUCCESS and Contabo deployment7756169546 SUCCESS. Both repository switches remain true; future main pushes use the restricted release path. See `.goal-harness/contabo-activation-20261113/verification.json` for exact runtime and artifact proof.

Actual authenticated desktop and430px mobile channel drawer inspected. Exact YouTube link opened the expected channel in a new tab. Admin test record saved, survived reload, then cleared and reload verified; no test email remains. Current UI includes a concurrent external channel addition (3visible YouTube channels); it was preserved. Original User/Organization/Integration/Post/Media records and original upload bytes preserved, except the expected test-channel updatedAt change; concurrent work added1Integration and7Post/Media. OAuth/config/startup guard hashes, port34007 loopback,4GiB/2CPU limits, networks and every unrelated container ID/state remained intact. No new video upload/publication was performed.

Cloned-DB private preview, archive readback/hash validation and actual candidate-ready failure/old-image recovery drill passed. Source/recovery backups remain. The release replaces only the app container; this release took approximately147seconds from recreate start to readiness verification, so allow a restart window. Preview namespace `item79-release-preview` is retained/reused; disposable preview containers/network and temporary registry credentials were removed. Root-owned deployment entry point updates require deliberate admin installation; Actions cannot alter its root code.

Final documentation-only evidence commit uses `[skip ci]` to avoid another app restart. The deployed revision above remains the exact runtime revision; final documentation does not change runtime source. Existing untracked `.goal-harness/item79-channel-customization/SESSION_STOP_20261113.md` is preserved.

# Historical stop snapshot — superseded by explicit resume above

Do not auto-resume. Canonical handoff: .goal-harness/item79-channel-customization/SESSION_STOP_20261113.md. Code/GitHub delivery complete; Contabo customization and automatic deployment still NOT applied. Global rule replacement/application unverified. Stop record only, no new commit/push/deployment.

# Historical GitHub-only source delivery snapshot — 2026-11-13

Repository: https://github.com/lsk7209/postiz-item79. Workspace: D:/program-codex/postiz-item79.
Baseline is exact operating upstream v2.25.3 commit a5affe62c74e39c1e7ac960d50d8418b807d532c, pinned image in Dockerfile.item79.

Implemented exact-ID YouTube sidebar links and per-channel Google email records. Only org ADMIN/SUPERADMIN can edit labels; malformed or stale edits fail closed, other provider settings and reserved labels preserved. Disconnected channels retain reconnect behavior. Generic settings editor hides reserved email. No database schema changes or identity inference.

Validation: Node8 + Python2 tests PASS; frontend production build/TypeScript PASS; backend final tsc PASS; independent scoped review no remaining blocker. Feature fe8680c pushed; GitHub checks run43353271667 SUCCESS.

Current delivery is GITHUB ONLY. Contabo postiz.item79.com remains unchanged. Image/build and deploy switches unset; jobs skipped. Prepared Dockerfile and forced-command deploy script need separately permitted activation, dedicated restricted SSH/registry setup, actual image/preview/persistence/rollback validation. Do not enable as a workaround for this boundary. See ITEM79.md and .goal-harness/item79-channel-customization/STATUS.md.

Google emails are administrator records, not API-verified ownership. Initial labels not seeded. Production Google authentication, tokens, queues, database/uploads and unrelated sites remain intact.
