#!/bin/bash
# Health Check Runner - runs healthcheck every minute + starts dashboard
# Usage: ./run.sh                        (run checker + dashboard on default host:port)
#        ./run.sh check                  (single check, for cron)
#        ./run.sh dashboard [host] [port] (dashboard only, optional host/port)
#        ./run.sh all [host] [port]       (both, optional host/port)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

MODE="${1:-all}"
HOST="${2:-}"
PORT="${3:-}"

DASH_ARGS=""
[ -n "$HOST" ] && DASH_ARGS="$HOST"
[ -n "$PORT" ] && DASH_ARGS="$DASH_ARGS $PORT"

case "$MODE" in
  check)
    python3 healthcheck.py
    ;;
  dashboard)
    python3 dashboard.py $DASH_ARGS
    ;;
  all)
    echo "Starting dashboard in background..."
    python3 dashboard.py $DASH_ARGS &
    DASH_PID=$!
    trap "kill $DASH_PID 2>/dev/null; echo 'Stopped.'; exit 0" INT TERM

    # Show bind info
    CFG_HOST="${HOST:-$(python3 -c 'import json; print(json.load(open("config.json")).get("dashboard_host","0.0.0.0"))')}"
    CFG_PORT="${PORT:-$(python3 -c 'import json; print(json.load(open("config.json")).get("dashboard_port",8111))')}"
    echo "Dashboard: http://${CFG_HOST}:${CFG_PORT}"
    echo "Starting health checks every 60 seconds (Ctrl+C to stop)..."
    echo ""

    while true; do
      python3 healthcheck.py
      echo ""
      sleep 60
    done
    ;;
  *)
    echo "Usage: $0 [check|dashboard|all] [host] [port]"
    echo ""
    echo "Modes:"
    echo "  check                  Run a single health check (for cron)"
    echo "  dashboard [host] [port] Start dashboard only"
    echo "  all [host] [port]       Start dashboard + run checks every 60s"
    echo ""
    echo "Examples:"
    echo "  $0                     # all on default 0.0.0.0:8111"
    echo "  $0 dashboard 127.0.0.1 9090"
    echo "  $0 all 0.0.0.0 8080"
    exit 1
    ;;
esac
