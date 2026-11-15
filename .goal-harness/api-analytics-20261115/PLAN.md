# Plan

1. Diagnose exact production/project identity without exposing credentials. DONE: three grants valid; Analytics API missing in postiz-item79/402500548053.
2. Enable only youtubeanalytics.googleapis.com. DONE: detailed reports work without login.
3. Fix exact-channel query, saved-grant retry and empty/error UX in web-only files; deterministic tests and independent review. DONE locally.
4. Back up and install only reviewed exact root release policy; preserve runtime closure/schema/worker guards.
5. Commit/push to existing GitHub/Contabo automatic warm release. Require CI image build, isolated preview, backup, worker identity and schema checks.
6. Compare public production API responses against direct exact-channel Google reports for all 3 channels x7/30/90. Legitimate empty reports are no-data, never fabricated zeros. Verify deployed revision/bundle and unchanged publisher.

Rollback: existing warm-slot rollback restores previous route; original publisher/backups remain. No change to shared worker source. Deliberate exact-file Dockerfile/source-policy exception reviewed; no broadened arbitrary paths.
