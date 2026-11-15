#!/bin/bash
set -euo pipefail
check_dir=/tmp/item79-analytics-check-20261115
mkdir -p "$check_dir"
git -C /mnt/d/program-codex/postiz-item79 archive HEAD | tar -x -C "$check_dir"
for source in apps/backend/src/api/routes/channel-analytics.ts apps/backend/src/api/routes/analytics.controller.ts apps/backend/src/public-api/routes/v1/public.integrations.controller.ts apps/frontend/src/components/platform-analytics/render.analytics.tsx apps/frontend/src/components/platform-analytics/platform.analytics.tsx; do
    cp "/mnt/d/program-codex/postiz-item79/$source" "$check_dir/$source"
done
if [ ! -e "$check_dir/node_modules" ]; then ln -s /opt/postiz-item79-review/node_modules "$check_dir/node_modules"; fi
cd "$check_dir"
/opt/shortsdog-runtime/node-v22.23.4-linux-x64/bin/node node_modules/typescript/bin/tsc --noEmit --incremental false -p apps/backend/tsconfig.build.json
