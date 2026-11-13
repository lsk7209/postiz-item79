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

**Automatic deployment is active.** See `PROJECT_STATE.md`,
`.goal-harness/operations-hardening-20261113/verification.json` and
`ops/ITEM79-OPERATIONS.md` for current evidence and recovery procedures.
Main-push run43374466169 and Contabo deployment7758307067 succeeded. The public
web runs `e46520f1`; the original `2c951cf3` all-in-one container remains the sole
publishing orchestrator and live fallback. Both delivery variables stay enabled.
Initial customization link/save/reload/clear checks were completed in the prior
activation; this follow-up rechecked the actual authenticated calendar and channels.

Main pushes run deterministic tests, source compatibility policy, immutable image
build/push and the restricted root-owned deploy entry point. A new web-only blue or
green slot passes cloned-DB preview and readiness before the dedicated proxy route
switches. It never starts an orchestrator or pushes a schema. The original app is
not recreated during ordinary releases; previous web slots remain warm and busy
connections are protected before reuse or failed-candidate cleanup. Failure restores
the exact prior route and verifies public recovery; interrupted releases reconcile a
durable journal. Actual switch/rollback and successful Actions deployment were tested.
The external probe observed3,140requests without failure over about28minutes; this
does not prove absolute zero downtime between samples.

Keep the exact existing project, startup dependency/OAuth Nginx guard, original
4GiB/2CPU app cap and loopback34007, secrets, databases, queues and uploads intact.
Web slots use loopback34008/34009 with2GiB/1CPU limits. Live schema diff, retained
worker runtime closure, original container/PID/restart counts and selected task-queue
sentinels are checked. Routine source policy rejects worker/shared contract/schema/
dependency/base-image changes; those require deliberate compatibility review.
No automatic schema migration or image rollback as a database rollback is allowed.

The dedicated deployment key has no interactive shell, PTY, forwarding or general
Docker/sudo access. It accepts only an exact Item79 image digest and stdin JSON with
revision, source-policy fields and a short-lived `packages:read` registry credential.
Temporary registry credentials are removed after pull. Server privileged code updates
require reviewed root installation; Actions cannot replace it. Existing environment
secrets `CONTABO_DEPLOY_KEY`, `CONTABO_HOST`, `CONTABO_USER`, `CONTABO_KNOWN_HOSTS`
and switches `ITEM79_IMAGE_BUILD_ENABLED`/`CONTABO_DEPLOY_ENABLED` remain in use.

Preview reuses `item79-release-preview`, with cloned PostgreSQL, private Redis,
read-only uploads and a fixed internal Temporal relay; web has no outbound internet
or publishing worker. Disposable containers/network are cleaned and private recovery
evidence retained. Image pulls reserve12GiB; snapshot archive files are read back
and hashed. Automatic daily encrypted source backup and independent OVH encrypted
storage/restore checks are active. Existing backups are retained without pruning.
Availability and deployment-failure monitoring runs on OVH; actual message delivery
is still waiting for the user's recipient/provider configuration. No alert has been
sent. This workflow does not upload or publish videos.

## Source license

This fork retains upstream AGPL-3.0 licensing. Corresponding customized source is
available at https://github.com/lsk7209/postiz-item79. Do not include account email
records, private videos, tokens, `.env` files or database backups in the repository.
