- Existing Node channel/account tests and Python deployment guards.
- New backup encrypted-export path guards, archive corruption/path/duplicate/symlink rejection, failure scratch cleanup, storage reserve enforcement and receipt integrity.
- Real source age-encrypted snapshot, pinned SSH read-only export, OVH age authentication, encrypted Restic snapshot and restore/hash of every file; disposable network-none PostgreSQL restore.
- Monitor outage thresholds/recovery/deploy-failure dedupe/pending delivery; actual recipient test only after recipient/config confirmation.
- Source/Dockerfile/worker-contract policy and live Prisma diff, no worker in web slot, rollback journal/recovery and traffic-switch failures.
- Actual push release with public revision polling and before/after worker container/PID/pollers/data/upload/config/other-service invariants; authenticated UI smoke.

Final result: Linux Actions34Python+8Node tests PASS,0skips; Windows Python34run with1symlink-privilege skip, Node8PASS. Actual PostgreSQL/Temporal/Redis isolated restore,91file post-release Restic restore/hash, full repository read-all check, switch/failure rollback, final successful Actions release,3,140HTTP requests0failures and authenticated calendar/3channels observed. Source-policy/OAuth config/runtime/schema/container invariants passed. No actual notification delivery test possible without the intended recipient/provider; do not mark it passed.
