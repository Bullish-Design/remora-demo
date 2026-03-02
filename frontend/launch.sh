#!/usr/bin/env bash
# launch.sh — Start both the graph viewer and open Neovim for the Remora demo.
#
# Usage:
#   ./launch.sh                    # defaults
#   ./launch.sh --port 9000        # custom graph viewer port
#   ./launch.sh --no-browser       # skip opening browser
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEMO_DIR="$SCRIPT_DIR/remora_demo/project"
DB_PATH="$DEMO_DIR/.remora/indexer.db"

PORT=8420
NO_BROWSER=0

# Parse flags
while [[ $# -gt 0 ]]; do
    case "$1" in
        --port) PORT="$2"; shift 2 ;;
        --no-browser) NO_BROWSER=1; shift ;;
        *) echo "Unknown flag: $1"; exit 1 ;;
    esac
done

echo "Remora Demo"
echo "==========="
echo "Demo project: $DEMO_DIR"
echo ""

# Ensure .remora directory exists
mkdir -p "$DEMO_DIR/.remora"

# Start graph viewer in background
echo "Starting graph viewer on http://127.0.0.1:$PORT ..."
python -m graph --db "$DB_PATH" --port "$PORT" &
GRAPH_PID=$!
echo "Graph viewer PID: $GRAPH_PID"

# Wait a moment for the server to start
sleep 1

# Open browser (best-effort)
if [[ "$NO_BROWSER" -eq 0 ]]; then
    if command -v xdg-open &>/dev/null; then
        xdg-open "http://127.0.0.1:$PORT" 2>/dev/null &
    elif command -v open &>/dev/null; then
        open "http://127.0.0.1:$PORT" &
    fi
fi

# Start Neovim with the demo project
echo "Opening Neovim..."
cd "$DEMO_DIR"
nvim src/configlib/loader.py

# Cleanup: kill graph viewer when Neovim exits
echo "Shutting down graph viewer..."
kill "$GRAPH_PID" 2>/dev/null || true
wait "$GRAPH_PID" 2>/dev/null || true
echo "Done."
