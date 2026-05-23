#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

stop_bot() {
  local stopped=0

  if ! command -v pgrep >/dev/null 2>&1; then
    return 0
  fi

  while IFS= read -r pid; do
    [ -z "$pid" ] && continue
    cmd="$(ps -p "$pid" -o args= 2>/dev/null || true)"
    case "$cmd" in
      *"$ROOT"*"main.py"*)
        echo "Stopping bot process $pid"
        kill "$pid" 2>/dev/null || true
        stopped=1
        ;;
      *"uv run python main.py"*)
        if [ "$(pwd -P 2>/dev/null || pwd)" = "$ROOT" ] || pgrep -P "$pid" -f "$ROOT/.venv" >/dev/null 2>&1; then
          echo "Stopping uv process $pid"
          kill "$pid" 2>/dev/null || true
          stopped=1
        fi
        ;;
    esac
  done < <(pgrep -f 'main\.py|uv run python main\.py' 2>/dev/null || true)

  if [ "$stopped" = 1 ]; then
    sleep 1
  fi
}

stop_docker() {
  if command -v docker >/dev/null 2>&1; then
    docker rm -f express-course >/dev/null 2>&1 || true
  fi
}

case "${1:-}" in
  install)
    uv sync
    ;;
  stop)
    stop_bot
    stop_docker
    ;;
  run)
    stop_bot
    uv run python main.py
    ;;
  docker-run)
    stop_bot
    stop_docker
    docker build -t express-course .
    docker run --rm --name express-course \
      --env-file .env \
      -v "$ROOT/.env:/app/.env:ro" \
      -v "$ROOT/system.txt:/app/system.txt:ro" \
      express-course
    ;;
  *)
    echo "Usage: $0 {install|stop|run|docker-run}"
    exit 1
    ;;
esac
