#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 /path/to/MISR_UAT_granule.nc" >&2
  exit 2
fi

uv run python -m harmony_compositor_service.cli \
  --input "$1" \
  --config examples/misr_dhr_natural_color_compositor_config.json \
  --schema config/config_schema.json \
  --settings config/settings.json
