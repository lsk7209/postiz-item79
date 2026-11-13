1. Read handoff, inspect repository and live isolated resources, review release risks.
2. Harden only concrete release defects; run focused tests; build immutable image using GitHub Actions with deploy disabled.
3. Back up live data/config; validate isolated preview; install restricted credential and exercise rollback.
4. Enable automatic deployment; push committed reviewed changes; verify actual deployed revision and public UI/persistence.
5. Record evidence, operating instructions and current PROJECT_STATE.
