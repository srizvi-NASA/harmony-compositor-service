"""Standalone CLI for local Compositor development and UAT-granule testing."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from harmony_compositor_service.adapter_utils import load_and_prepare_settings
from harmony_compositor_service.config_validator import load_and_validate_config
from harmony_compositor_service.core import process_product


def main() -> None:
    """Compose one local granule using one local external-format configuration."""
    parser = argparse.ArgumentParser(description="Harmony Compositor local CLI")
    parser.add_argument("--input", required=True, help="Local input netCDF granule")
    parser.add_argument(
        "--config",
        default="examples/misr_dhr_natural_color_compositor_config.json",
        help="Local Compositor configuration JSON",
    )
    parser.add_argument(
        "--schema",
        default="config/config_schema.json",
        help="Compositor configuration JSON schema",
    )
    parser.add_argument(
        "--settings",
        default="config/settings.json",
        help="Service settings JSON",
    )
    args = parser.parse_args()

    settings = load_and_prepare_settings(Path(args.settings))
    config = load_and_validate_config(args.config, args.schema)

    source = Path(args.input).expanduser().resolve()
    if not source.exists():
        parser.error(f"Input granule does not exist: {source}")

    staged = Path(settings["data_dir"]) / source.name
    if source != staged.resolve():
        shutil.copy2(source, staged)

    output = process_product(settings, config, staged.name)
    print(output)


if __name__ == "__main__":
    main()
