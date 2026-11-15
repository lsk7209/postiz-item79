# Acceptance

| Criterion | Result | Evidence |
|---|---|---|
| Exact host/project identity | PASS | pinned SSH; postiz-item79/402500548053 |
| Missing service activated without channel login | PASS | Google service operation recorded in EVIDENCE.md |
| Saved grants refresh automatically | PASS |3expired-token report clients; no persisted credential changes |
| Exact-ID/org/period scope and classified errors | PASS |17Node tests, backend tsc, independent actual diff review |
| API-only retry/no automatic OAuth redirect | PASS | source regression test and production build |
| Actual requested runtime deployed | PASS | caf8bfa2, immutable imagef57599be..., GitHub43684914044 |
|9period/channel reports match direct reports | PASS | E:logs/production-verification.jsonl; full daily values compared |
| API auth/date/missing-ID boundaries | PASS |401/400/404/401 actual production |
| Worker/config/schema/recovery preserved | PASS | runtime-before/after equality; actual release guards and warm blue fallback |
| User E: storage direction | PASS | E:source snapshot, temp/log paths, runtime build and storage receipt |

Limits: private analytics still require a valid saved grant; no new channel login was performed. Other providers retain existing backend behavior. Visual browser inspection unperformed; API/compiled runtime evidence does not claim screenshot inspection. CI export failure cause remains unproven; no production workaround or safety bypass.
