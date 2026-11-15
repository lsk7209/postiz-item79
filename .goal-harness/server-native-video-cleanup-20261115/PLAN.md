# PLAN

1. Freeze old Windows writer, inspect old intents/quarantine and seed observed timestamps.
2. Install server coordinator + bounded restricted recovery/reader helpers and dedicated SSH keys.
3. Add PC local-only receipt catch-up; pin exact local asset set per operation.
4. Fault/permission tests and independent review.
5. Live audit, OVH exact restore verification, server timer activation and PC-off-path service execution; then PC local-only task/logon catch-up activation.
6. Verify workers/config preserved, record source hashes, commit/push and docs.
