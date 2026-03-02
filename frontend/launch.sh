#!/usr/bin/env bash
set -euo pipefail

# Launch the Remora Graph Viewer
exec python -m graph "$@"
