# Risk Notice

Task: move authorized automatic video cleanup to Contabo so PC shutdown cannot stop it.
Impact Scope: existing Item79 gate unchanged; new scoped Contabo timer/coordinator, dedicated OVH backup-verifier SSH identity, dedicated Contabo read-only receipt-reader SSH identity and corresponding PC private keys. No existing personal/admin key copied between hosts. Dedicated accounts only permit fixed root-owned bounded-JSON helpers via restricted authorized keys/sudo command.
Approval: current user explicitly requests PC-independent automation, earlier deletion/backup/retention scope retained. No new purchases, external hosting accounts, backup pruning, app/worker/schema/DNS/mail changes.
Rollback: stop/disable new timer; keep existing Windows task disabled until reviewed configuration chosen; preserve all old task XML, state, recovery snapshots and receipts. Interrupted quarantines reconcile via unchanged gate.
Safeguards: old Windows APPLY disabled before cutover; no active/ambiguous old intents or quarantines may be silently migrated. Server owns first-observation timestamps and completed removal receipts. PC mode can only read/export/local-check through a cryptographically restricted SSH key, then remove exact enrolled local copies when online.
