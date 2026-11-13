# Changes

| File | Change | Purpose |
|---|---|---|
| ops/contabo-deploy.py | Scoped registry auth, identity/schema checks, cloned-DB private preview, archive validation, disk guard, recovery readiness | Safe actual automatic release |
| .github/workflows/item79.yml | Read-only deploy token and image-layer cache | Restricted repeatable delivery |
| Dockerfile.item79 | Move revision labels after compiled layers | Reuse identical tested app build for metadata-only revisions |
| tests/test_deploy_guard.py | Release/rollback/preview/schema/disk/archive behavioral checks | Prove failure recovery and fail-closed boundaries |
| .dockerignore | Exclude local secrets/runtime evidence | Keep build context private |
| ITEM79.md, PROJECT_STATE.md, activation harness | Current deployment instructions and evidence | Accurate continuation |
