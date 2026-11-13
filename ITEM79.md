# Item79 Postiz customization

Source baseline: upstream v2.25.3, commit a5affe62c74e39c1e7ac960d50d8418b807d532c.
The original upstream repository and all original local changes remain untouched.

## Channel sidebar

YouTube profile pictures and names open the exact validated channel ID in a new tab.
Disconnected/incomplete connections retain their reconnect flow. Other networks retain
their existing behavior. The existing channel menu and drag region remain available.

Each YouTube channel can record its connected Google email under its name. Click the
label to edit or clear it. This is explicitly an operator record, **not independently
verified OAuth ownership**. Brand-account OAuth userinfo and the Postiz login email
must never be used to infer an owner's personal Gmail. Unknown accounts start blank.
Only organization admins can edit the record through a dedicated endpoint. Concurrent
updates fail with a conflict; generic provider settings cannot overwrite this record.
The record uses org-scoped existing `additionalSettings`, does not alter tokens, and
is hidden from the generic boolean settings editor. No DB schema change is required.

## Delivery state and activation

**Activation authorized 2026-11-13; see PROJECT_STATE.md and the Contabo activation harness for verified current release evidence.**
Actual automatic main-push run43357711188 completed all three jobs successfully;
Contabo runs2c951cf3. Public authenticated desktop/mobile link and save/reload/clear
checks passed. Both delivery variables remain enabled. The final documentation-only
evidence commit skips CI to avoid a redundant app restart; runtime code is unchanged.
CI runs deterministic metadata/link tests on push. Image build and production deploy
are both disabled unless their explicit repository variables are enabled. No deploy
key, registry credential or production environment file is committed.

The production release path requires:

1. Build and test the complete image in `Dockerfile.item79`, review the digest and
   preview the actual full/mobile sidebar and metadata persistence before release.
2. Configure a dedicated restricted SSH key and root-owned forced command for
   `ops/contabo-deploy.py`. Pin the existing server host key; no auto-accept.
3. Use only the existing `/opt/postiz-center-20261112` project. Keep its startup guard,
   CPU/memory caps, private app port, network, secrets, database and uploads intact.
4. Pass the deploy job's short-lived `packages:read` token over SSH stdin. The server
   logs in using a private temporary Docker configuration removed after pull; no
   permanent registry token or unrestricted admin key is supplied to Actions.
5. Preserve a DB backup and source recovery before release. The upstream image runs
   Prisma db push on startup. This patch has no schema changes; future
   schema updates require their own migration review and data recovery plan.
6. Configure secrets `CONTABO_DEPLOY_KEY`, `CONTABO_HOST`, `CONTABO_USER`,
   `CONTABO_KNOWN_HOSTS`; enable `ITEM79_IMAGE_BUILD_ENABLED` and, only after all checks,
   `CONTABO_DEPLOY_ENABLED`. Forced command must deliberately enable
   `ITEM79_ALLOW_DEPLOY=true` after authorization. The root-owned wrapper supplies this
   gate; the dedicated SSH key is restricted to exact Item79 digest releases.

The prepared deploy script only replaces the app's pinned image, serializes releases,
checks the OCI source revision, unchanged schema, startup guard and resource limits,
tests a loopback-only preview against a cloned DB with read-only uploads, separate Redis,
an isolated Temporal namespace and web processes only (no publishing workers),
backs up the DB/config before every replacement, checks login/closed registration and
the protected custom route, and restores the previous compose plus checks recovery
readiness on failure. `main` pushes run checks, build/push an immutable image and deploy
when the two explicit repository switches are enabled. Releases are serialized.
Image rollback is not a database rollback. Production authentication, video scheduling,
volume continuity, and a full rollback drill must be verified on actual release.
Those activation checks have now passed; future scheduled-post outcomes are separate
from this release verification. The app is recreated during release (restart window).

The deployment credential has no interactive shell, PTY, port forwarding or general
Docker/sudo access. Its root-owned entry point accepts only
`deploy ghcr.io/lsk7209/postiz-item79@sha256:<64 hex>`, and a stdin JSON object containing
the exact source `revision`, `registryUser` and short-lived `registryToken`. The workflow
checks are required dependencies of release jobs. This workflow does not publish videos.

Preview reuses the dedicated `item79-release-preview` Temporal namespace, with no workers
and cron disabled. A fixed internal TCP7233 relay reaches Temporal without modifying its
network attachments. Every preview uses unique disposable web/DB/Redis/relay containers;
dump/config evidence remains private under the project. Release fails closed if cleanup
is incomplete. Image pulls need at least12GiB free; recovery backup additionally reserves
twice the runtime-file size plus12GiB. Every archived runtime file is read back and hashed.

## Source license

This fork retains upstream AGPL-3.0 licensing. Corresponding customized source is
available at https://github.com/lsk7209/postiz-item79. Do not include account email
records, private videos, tokens, `.env` files or database backups in the repository.
