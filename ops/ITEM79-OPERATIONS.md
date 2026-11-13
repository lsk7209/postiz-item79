# Item79 operations

Scope: `lsk7209/postiz-item79`, `https://postiz.item79.com`, Contabo
`vmi3690013:/opt/postiz-center-20261112`, and the dedicated Item79 paths on
OVH `vps-ce781f0f`. Root-owned tools live in `/usr/local/lib/item79`.
Other projects, mail, DNS, accounts, scheduled posts and existing backups are
outside these tools' mutation scope. No backup pruning is enabled.

## Backup and independent verification

Contabo `item79-backup.timer` runs daily at 03:15 Asia/Seoul (18:15 UTC).
`item79-backup.py` takes individual Postiz and Temporal custom-format PostgreSQL
dumps, a Redis RDB, uploads, configuration and the dedicated proxy route. It
records every file's SHA-256, reads back the archive, encrypts with age, and
exports ciphertext only in `/var/lib/item79-backup-export`. A shared deployment
lock prevents concurrent release snapshots. Plaintext staging is removed in
`finally`; original recovery backups are retained. Twelve GiB remains reserved
on the source, including during streaming writes.

OVH `item79-offsite.timer` pulls hourly at minute25 UTC. Its dedicated SSH key
can execute only `status` or `fetch <snapshot-id>` as `item79-backup-reader`;
there is no general shell, forwarding, Docker access or sudo through that key.
The source host key is pinned. `item79-offsite.py` verifies ciphertext and
manifest hashes, authenticates/decrypts age, rejects unsafe archive paths, saves
to the encrypted Restic repository and restores the exact Restic snapshot to
check every file again. It reserves four GiB plus temporary processing space.
The isolated Restic repository, cache and receipts are under
`/var/lib/item79-offsite`; private keys/password/config are root-only under
`/etc/item79-ops`. Temporary plaintext copies are removed after each attempt.

`item79-offsite-check.timer` runs a full `restic check --read-data` weekly at
Sunday01:00 Asia/Seoul. No automatic `forget`, `prune`, source deletion or
recovery-backup deletion is configured. Source ciphertext accumulates; monitor
warnings trigger at export>8GiB/source free<16GiB, OVH free<6GiB or verified
backup age>30hours. Continuous storage is finite and needs a deliberate
retention/capacity decision before those limits. A failed snapshot or exhausted
reserve fails closed and retains the last verified backup.

Inspect safely with `systemctl status item79-backup.timer` on Contabo and
`systemctl status item79-offsite.timer item79-offsite-check.timer` on OVH. The
offsite `latest.json` and `receipts/<id>.json` contain verification metadata,
not application secrets. Service diagnostics are private; do not publish dumps,
config files, stderr diagnostics, keys or database contents.

First restore was tested in disposable PostgreSQL and Redis containers with
`--network none`; application/publishing workers were never started. Each dump
is internally consistent, but PostgreSQL databases, Redis and live uploads are
captured at different instants. This is not an atomic cross-service checkpoint.
During disaster recovery, restore only into isolated infrastructure first;
reconcile Temporal schedules and pending/unknown provider outcomes before
allowing a publishing worker to poll. Hash success alone is not whole-service
recovery proof. Preserve the original source and all recovery evidence.

An additional key/password recovery package is encrypted with Windows
CurrentUser DPAPI at `C:/Users/dlatj/.ssh/item79-recovery/offsite-keys.dpapi`,
with inheritance removed and only this user's SID and SYSTEM granted access.
Its in-memory decrypt roundtrip was verified. It requires the same Windows
user/device context; it is not a portable plaintext key or a substitute for a
separately protected offline recovery plan. Never commit it or display its
decrypted values in a tool log.

## Monitoring and notification setup

OVH `item79-monitor.timer` checks the public login and closed-registration API
every minute. Three consecutive failures create a down event; two good checks
create a recovery event. Every five minutes it checks this repository's public
main-branch workflow for failed push/dispatch runs and the source export's
capacity/accessibility. Backup age and offsite disk headroom are checked too.
Events are saved before delivery and retried until the configured provider
acknowledges; process interruption after provider acknowledgement may duplicate
a message. This is not an exactly-once transport.

Actual delivery requires the user's intended recipient and a working provider
configuration in root600 `/etc/item79-ops/notify.json`. Do not infer a recipient
from Git identity, connected social accounts, or unrelated hosting services.
No recipient was configured or delivery claimed during initial installation.
The current monitor remains useful for saved health/backup observations.

Supported config shapes (replace placeholders privately, never commit values):

```json
{"provider":"telegram","botToken":"PRIVATE","chatId":"INTENDED_CHAT"}
{"provider":"discord","webhookUrl":"https://discord.com/api/webhooks/PRIVATE"}
{"provider":"smtp","host":"SMTP_HOST","port":465,"from":"SENDER","to":"INTENDED_RECIPIENT","username":"PRIVATE","password":"PRIVATE"}
```

SMTP can use `"starttls":true` with port587. Test only the explicitly intended
recipient; require an actual provider acknowledgement and record metadata
without secrets. Simulated threshold tests do not establish delivery. Monitor
state is `/var/lib/item79-offsite/monitor-state.json`. Check service success and
`siteHealthy`, `githubObservable`, `offsiteBackupFresh`, `notificationConfigured`
and pending delivery there. The GitHub observer uses unauthenticated API access,
paginated searches and a durable cursor that revisits unfinished runs. Two
consecutive API/coverage failures queue a separate monitoring-gap alert; recovery
queues another event. A failed scan never advances the cursor. GitHub's
[filtered-search limit](https://docs.github.com/en/rest/actions/workflow-runs)
of1,000 results is treated as a coverage failure rather than silently truncating.
API outages/rate limits leave `githubObservable:false`, not a success claim.

## Warm web releases and rollback

The existing `postiz-center` app remains the sole publishing orchestrator and
live fallback. Routine releases never recreate it. Blue and green Compose
projects contain only frontend/backend, use the existing app environment and
uploads, and bind to loopback34008/34009. `RUN_CRON` is empty and no startup
schema push or orchestrator command runs in a web slot. Slots have2GiB/1CPU
limits; release requires more than4GiB available memory.

Before switching, the root-owned deploy entry point checks the immutable image
revision, schema bytes, live schema diff, retained worker runtime closure,
container/PID/restart counts and selected Temporal task-queue poller identities
(main workflow/activity and YouTube activity sentinels; not every provider/email
queue). The process identity proves the release did not replace the worker;
these sentinel checks do not prove comprehensive queue health.
The CI/source policy rejects changes to the pinned Dockerfile/base image,
backend/shared worker contracts, schema, packages or lockfile. Unsupported
changes require deliberate compatibility/migration review and root policy
installation; do not weaken the allowlist just to make a release pass.

The candidate first passes a cloned-DB private web preview, then a recovery
snapshot and warm public-network readiness. Only the dedicated
`/data/coolify/proxy/dynamic/postiz-item79.yml` service target is atomically
replaced. Public frontend and backend responses must carry the intended
`X-Item79-Revision`. Post-switch checks require the original worker/pollers and
live schema unchanged. The previous web slot remains warm. Before reusing the
inactive slot, Nginx active connections must become quiet; otherwise release
aborts to preserve active uploads.

`web-release.pending.json` journals the old route/state before candidate
creation. Normal errors restore the exact prior route, verify public recovery,
and stop only the failed candidate. Interrupted releases reconcile the journal
before another release. Successful state is `web-release.json`; route backups
are under the existing root-only `backups/release-*` directories. Never use
`docker compose down` on the original stack as a release shortcut.

For an urgent manual rollback, take the same `.deploy.lock`, verify the saved
route belongs exclusively to `postiz.item79.com`, confirm its previous target
is healthy, save current state, atomically restore that route, and verify the
public revision and unchanged original worker. Reconcile `web-release.json`
with the restored slot; do not leave route/state inconsistent. Keep the failed
image, databases, uploads and backups for investigation. Do not blindly revert
to an older backend after any deliberate schema change.

Updating root deployment/backup/monitor tools requires an administrator to
review and install these exact source files with root ownership. Actions holds
only a forced-command deploy key and short-lived registry read token; it cannot
replace the server's privileged code. Save the previous installed scripts under
the scoped backup directory before updating. Timers and root-only config are
installed directly on the verified hosts, not stored with credentials in Git.
