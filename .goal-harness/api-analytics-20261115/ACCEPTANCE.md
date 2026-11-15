# Acceptance

| Criterion | State | Evidence |
|---|---|---|
| Exact host/project identity | PASS | pinned SSH and Google project metadata |
| Missing API activated without channel login | PASS | Google service activation operation |
| Three saved refresh grants work | PASS | verify-refresh.py |
| Exact-ID/ownership/cache/error correctness | PASS local | Node17, backend tsc, independent actual diff review |
| API-only retry; no OAuth redirect | PASS local | source regression test |
| Actual requested runtime deployed | PENDING | CI/Contabo |
| Nine period/channel reports match direct exact reports | PENDING | production verification |
| Publisher/runtime/schema preserved | PENDING deployment | warm release guards |

Limit: revoked access requires real owner consent; no API bypass. App/API-key auth remains required. New channels may legitimately have no report rows. Other providers retain existing backend implementation.
