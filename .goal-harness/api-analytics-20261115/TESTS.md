# Tests

- Local Node17/17 PASS; CI17Node+35Python=52/52 PASS. Windows Python34PASS/1symlink permission skip; Linux skip absent.
- Backend full tsc PASS in original isolated Linux check. CI complete backend build/declarations and frontend compile/TypeScript/static pages PASS; actual image built/pushed/deployed.
- New local E: backend runtime build PASS; output backend-runtime/apps/backend/src/api/routes/channel-analytics.js,5350bytes. First E: declaration emission failed TS2742 because reused dependency symlink points outside E:. Preserved failed outputs; runtime-only local build disables declarations, keeps full typechecking, emits into a fresh E: directory. CI still validates full declarations, no application source weakened.
- Production:3channels x7/30/90=9HTTP200 reports match exact-ID Google reports in every daily value/label; forced-expired in-memory clients refreshed saved grants successfully. No channel login or persistent credential update.
- Live boundaries: public API without key401; invalid period400; unknown channel404; private API without session401.
- Public/production revisioncaf8bfa2; original publisher/config equality PASS; actual release preview/schema/runtime closure/backup/warm rollback checks PASS.
- E: archive SHA256 and runtime artifact SHA256 recorded in storage-receipt.json. Raw logs stay E:.
- YAML/image/deploy shell syntax checked after final read-only disk-guard cleanup. No new application release required for final docs/local scripts/CI side-effect removal; measured pre-cleanup89GiB exceeds24GiB gate.

Unperformed: visual browser inspection (existing connection unavailable); no GUI restart. Known failures: initial red helper-missing test, one WSL quoting repair,3CIimage export143s, one E: declaration-path issue. All preserved in EVIDENCE.md; no export143 cause fabricated.
