# Item79 production operations hardening

User accepted the three proposed follow-ups and said 진행해 on2026-11-13: regular automatic DB/upload backup with storage outside Contabo, site/deploy failure alerts, and reduce release interruption.

Acceptance: scheduled backup active with an actual encrypted offserver copy and isolated restore/hash proof; external availability and failed-deploy alert path tested without publishing secrets; warmed web release switches traffic while retaining the existing publishing worker and measured public interruption is reduced from the147second baseline. Exactly one original publishing worker process, unchanged schema/OAuth/jobs/uploads/mail/domain and unrelated services. Commit/push/deploy actual changes and record exact runtime evidence.

Risk Notice: production scheduling, offserver confidential backups, alert delivery and application traffic handover. Explicit user authorization covers this Item79 scope. Verify both owned hosts/paths and intended alert recipient before activation. Encrypt offserver copies; use dedicated restricted credentials. Preserve all old source/recovery backups and current deployment rollback. No purchases, unrelated deployments, destructive production DB operations, account cancellations or Vercel changes.
