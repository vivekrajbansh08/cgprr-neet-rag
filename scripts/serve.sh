#!/usr/bin/env bash
# Start / stop the retrieval (8001), answer (8002) and predictor (8003) services on 127.0.0.1 with uvicorn (no Docker).
# PID files and service logs go to logs/. Usage: scripts/serve.sh start|stop
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p logs

SERVICES=("retrieval:neet_retrieval.app:app:8001" "answer:neet_answer.app:app:8002"
          "predictor:neet_predictor.app:app:8003")

start() {
  for spec in "${SERVICES[@]}"; do
    IFS=: read -r name module attr port <<<"$spec"
    pidfile="logs/${name}.pid"
    if [[ -f "$pidfile" ]] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
      echo "$name already running (pid $(cat "$pidfile"))"
      continue
    fi
    nohup uv run uvicorn "${module}:${attr}" --host 127.0.0.1 --port "$port" \
      >>"logs/${name}.log" 2>&1 &
    echo $! >"$pidfile"
  done
  for spec in "${SERVICES[@]}"; do
    IFS=: read -r name _ _ port <<<"$spec"
    for _ in $(seq 1 60); do
      if curl -fsS "http://127.0.0.1:${port}/health" >/dev/null 2>&1; then
        echo "$name: http://127.0.0.1:${port}  (health ok)"
        continue 2
      fi
      sleep 0.5
    done
    echo "$name did not become healthy on port $port; see logs/${name}.log" >&2
    exit 1
  done
}

stop() {
  for spec in "${SERVICES[@]}"; do
    IFS=: read -r name _ _ _ <<<"$spec"
    pidfile="logs/${name}.pid"
    if [[ -f "$pidfile" ]]; then
      pid="$(cat "$pidfile")"
      if kill -0 "$pid" 2>/dev/null; then
        pkill -P "$pid" 2>/dev/null || true
        kill "$pid" 2>/dev/null || true
        echo "stopped $name (pid $pid)"
      fi
      rm -f "$pidfile"
    fi
  done
}

case "${1:-}" in
  start) start ;;
  stop) stop ;;
  *) echo "usage: $0 start|stop" >&2; exit 2 ;;
esac
