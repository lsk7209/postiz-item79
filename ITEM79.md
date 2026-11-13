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

**Current delivery boundary: GitHub only. The Contabo site has not been updated.**
CI runs deterministic metadata/link tests on push. Image build and production deploy
are both disabled unless their explicit repository variables are enabled. No deploy
key, registry credential or production environment file is committed.

After deployment is separately permitted, an operator must:

1. Build and test the complete image in `Dockerfile.item79`, review the digest and
   preview the actual full/mobile sidebar and metadata persistence before release.
2. Configure a dedicated restricted SSH key and root-owned forced command for
   `ops/contabo-deploy.py`. Pin the existing server host key; no auto-accept.
3. Use only the existing `/opt/postiz-center-20261112` project. Keep its startup guard,
   CPU/memory caps, private app port, network, secrets, database and uploads intact.
4. Ensure the server can pull the package (public GHCR or a separately scoped read-only
   registry credential). Never reuse an unrestricted admin key for GitHub Actions.
5. Preserve a DB backup and source recovery before release. The upstream image runs
   Prisma db push on startup. This patch has no schema changes; future
   schema updates require their own migration review and data recovery plan.
6. Configure secrets `CONTABO_DEPLOY_KEY`, `CONTABO_HOST`, `CONTABO_USER`,
   `CONTABO_KNOWN_HOSTS`; enable `ITEM79_IMAGE_BUILD_ENABLED` and, only after all checks,
   `CONTABO_DEPLOY_ENABLED`. Forced command must deliberately enable
   `ITEM79_ALLOW_DEPLOY=true` after authorization. Current variables remain unset.

The prepared deploy script only replaces the app's pinned image, serializes releases,
checks login/closed registration, and restores the previous compose on failed readiness.
Image rollback is not a database rollback. Production authentication, video scheduling,
volume continuity, and a full rollback drill must be verified on actual release.

## Source license

This fork retains upstream AGPL-3.0 licensing. Corresponding customized source is
available at https://github.com/lsk7209/postiz-item79. Do not include account email
records, private videos, tokens, `.env` files or database backups in the repository.
