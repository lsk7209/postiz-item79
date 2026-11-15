#!/bin/bash
# Task-local E: build; existing Linux dependencies are read, never moved/modified.
set -euo pipefail
build_root=/mnt/e/codex-build/postiz-item79/api-analytics-20261115
test -d "$build_root/source"
mkdir -p "$build_root/tmp" "$build_root/logs"
export TMPDIR="$build_root/tmp"
export PATH="/opt/shortsdog-runtime/node-v22.23.4-linux-x64/bin:$PATH"
export NODE_OPTIONS=--max-old-space-size=4096
cd "$build_root/source"
if [ ! -e node_modules ]; then ln -s /opt/postiz-item79-review/node_modules node_modules; fi
# This local cache is a dependency symlink; do not emit portable package .d.ts
# declarations through its external physical paths. CI still runs the full build.
node node_modules/typescript/bin/tsc --incremental false --declaration false --outDir "$build_root/backend-runtime" -p apps/backend/tsconfig.build.json 2>&1 | tee "$build_root/logs/backend-build.log"
test -f "$build_root/backend-runtime/apps/backend/src/api/routes/channel-analytics.js"
printf '%s\n' 'E: backend runtime build PASS; output stays on /mnt/e/codex-build/postiz-item79/api-analytics-20261115/backend-runtime' | tee -a "$build_root/logs/backend-build.log"
