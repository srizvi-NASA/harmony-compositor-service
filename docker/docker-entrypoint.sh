#!/usr/bin/env bash
set -euo pipefail

# Arguments beginning with '-' are Harmony adapter arguments.
if [[ "${1:0:1}" = "-" ]]; then
  exec python -m harmony_compositor_service.adapter "$@"
fi

mode="$1"; shift
case "$mode" in
  composite)
    exec python -m harmony_compositor_service.adapter "$@" ;;
  local)
    exec python -m harmony_compositor_service.cli "$@" ;;
  *)
    exec "$mode" "$@" ;;
esac
