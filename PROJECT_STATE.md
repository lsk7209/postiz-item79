# API analytics without repeated channel login — 2026-11-15

Current task: VERIFYING_RELEASE. Evidence: `.goal-harness/api-analytics-20261115/STATUS.md` and `EVIDENCE.md`. Exact Google project postiz-item79/402500548053 was missing youtubeanalytics.googleapis.com; enabled using existing management auth. All3 saved channel grants refresh successfully without login. Existing MINE query can return wrong-channel reports; new web-only reader binds exact organization/channel/date and safe API errors, with API-only retry/no-data UI. No shared worker source or schema/dependency changes. Node17PASS, Python34PASS/1Windows symlink skip, isolated backend full tscPASS; independent actual diff review no blocker/high. Reviewed exact web/Dockerfile policy installed with prior root policy backup. CI/Contabo deployment and exact-channel public verification remain pending. Original publishing worker, queues, uploads, credentials, prior backups and unrelated dirty stop files preserved.

# Backup and warm release verified; notification recipient pending — 2026-11-13

Current state: WAITING_FOR_NOTIFICATION_DESTINATION. Canonical task evidence: `.goal-harness/operations-hardening-20261113/STATUS.md` and `verification.json`; recovery/operating guide: `ops/ITEM79-OPERATIONS.md`. Backup and release follow-ups are verified. Actual alert delivery is incomplete because the intended channel/recipient and private provider configuration are missing; the async question remains unanswered. Do not infer a recipient or report all three follow-ups complete.

Public web https://postiz.item79.com/launches runs commit `e46520f1b1ae795fee2b07f0c066cb5c06663756`, image `ghcr.io/lsk7209/postiz-item79@sha256:3a6c3fea7b71a6b03dc490722c2006afdf7e7ad94ed9469df461b7221c6550ad`, warmed blue slot. Actual push run43374466169 and Contabo deployment7758307067 SUCCESS; Linux CI34Python+8Node tests PASS. The original2c951cf3 app remains the sole publishing orchestrator/live fallback; it was never recreated. Its container/PID193/restarts0, schema/config/OAuth Nginx,78original upload hashes, original record IDs and185existing container IDs/states/start timestamps remain unchanged. Real switch/failure rollback and final authenticated calendar/3channels checked. External1662second probe observed3,140requests with0failures (median gap1s,max5.778s; no absolute zero-downtime claim). Final documentation-only commit skips CI; runtime code above stays exact.

Daily03:15KST encrypted source backup, hourly OVH encrypted Restic pull/full file restore+hash, weekly repository read-all timer and minute health monitor are enabled/active. Actual full repository check passed; initial Postiz/Temporal/Redis dumps restored in isolated network-none containers without any publisher. Latest post-release snapshot20261113T055740Z-fcffceb0 (91files) independently restored/hashed as Restic86395a1d7fccc0ef60de27aa9668e200c671c206d484f2f03c9efd90f206a66a. Source/offsite staging empty; all old backups preserved, no pruning. These prove artifact recovery, not cross-store atomic recovery or safe restart of publishing work; reconciliation remains required during disaster recovery.

OVH monitor observed a real failed deployment attempt43373836530 (safe startup guard rejection, fixed before successful release) and queued one deploy_failed event. Public site/GitHub/source/fresh-backup checks healthy; notify.json absent, deliveredCount0. After the user supplies the intended recipient, configure private provider settings and test actual delivery/recovery alerts; preserve the existing queued event and timers. No duplicate jobs, unrelated deployments, DNS/mail changes or social publishing occurred. Existing untracked channel-customization stop file remains untouched.

# Prior Contabo automatic deployment verified — 2026-11-13

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
