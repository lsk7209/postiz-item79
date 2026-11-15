# PLAN

1. Inspect production, backup and bounded local receipt conventions.
2. Implement exact provider/reference gate, OVH recovery verification, durable operation reconciliation and Windows exclusive-handle cleanup.
3. Test commit failure, file replacement, privacy/retention/references, acknowledgement loss, restart, backup failure and Windows active-file lock.
4. Independent destructive-operation review; resolve blockers.
5. Install pinned gate on confirmed Contabo and private runner/daily Windows task; run actual task, verify receipt/next trigger, commit/push only scoped code/evidence. No app rebuild required.
