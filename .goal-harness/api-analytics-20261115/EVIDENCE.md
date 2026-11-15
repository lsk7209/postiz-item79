# Evidence — 2026-11-15

Host vmi3690013/13.140.77.84 verified via pinned SSH; domain postiz.item79.com; initial web revision e46520f1b1ae795fee2b07f0c066cb5c06663756. Sole publisher postiz-center-app-1.

All3 saved tokens initially valid; Analytics API failed 403 accessNotConfigured for consumer projects/402500548053, service youtubeanalytics.googleapis.com. gcloud metadata confirms project postiz-item79=402500548053; only youtube.googleapis.com initially enabled. Enabling only missing service succeeded: operation acat.p2-402500548053-156117c9-d521-47ed-b6ba-9b027e7b7fec. No OAuth/client/billing changes.

After activation all direct MINE reports and 9 original production public API requests succeeded, but returned identical 5/28/88 daily-row counts across3channels. Existing provider ignores saved internalId. Exact-ID reports using saved refreshed grants returned distinct 2/0/5 row counts for Nov1–14, motivating source correction.

verify-refresh.py:3refresh+userinfo+exact-channel requests succeeded without new login, credentials refreshed only in memory. Initial verify-production.py removed no cache keys (all9emptyCacheRemoved=false); no other Redis state changed.

Local Node17/17 PASS; Python34PASS/1Windows symlink skip; isolated Linux backend full tsc --noEmit --incremental false PASS. Independent actual-diff review: no blocker/high; validated ownership, exact-ID, server-memory token refresh, cache isolation, safe424 errors avoiding app logout, API-only retry and worker-runtime compatibility. Medium limitations: other providers use legacy backend; revoked grant still needs real consent; actual expired-token behavior requires live comparison.

Main session retained; read-only explorer inherited runtime model; unsupported model overrides not attempted. Tokens/cost unmeasured. One local shell quoting retry; no ambiguous external side-effect retry. Final CI/deployment and exact-channel public API comparison pending.
