#!/bin/sh
set -eu
TASK_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
exec docker run --rm --network none --cpus 2 --memory 4g --entrypoint python -v "$TASK_ROOT:/app" -w /app "${GONGZHENG_IMAGE:-gongzheng-native:0.1.0}" -m gongzheng.cli "$@"
