"""Harmony adapter for the configuration-driven Compositor Service."""

from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import harmony_service_lib
from harmony_service_lib.util import download, stage
from pystac import Asset, Item

from harmony_compositor_service.adapter_utils import load_and_prepare_settings
from harmony_compositor_service.config_utility import get_compositor_config_from_source
from harmony_compositor_service.core import process_product
from harmony_compositor_service.exceptions import CompositorError


def _service_root() -> Path:
    """Locate the repository/runtime root in both local and Docker layouts.

    The Filtering Service container copies the package directly under
    ``/worker`` while local ``uv`` development imports it from ``src``.  Check
    both layouts so the adapter always finds the checked-in ``config`` folder.
    """
    module_path = Path(__file__).resolve()
    candidates = [Path.cwd(), module_path.parent.parent, module_path.parent.parent.parent]
    for candidate in candidates:
        if (candidate / "config" / "settings.json").exists():
            return candidate
    raise CompositorError("Unable to locate Compositor service config directory.")


class CompositorAdapter(harmony_service_lib.BaseHarmonyAdapter):  # type: ignore[misc]
    """Download a Harmony input, compose configured bands, and stage the result."""

    def process_item(self, item: Item, source: Any) -> Item:
        result = item.clone()
        result.assets = {}

        variables = source.process("variables") or []
        requested_variable = variables[0].name if variables else None
        if requested_variable:
            self.logger.info("Requested variable: %s", requested_variable)
        else:
            self.logger.info("No explicit variable was requested; using first config URL found.")

        base = _service_root()
        settings = load_and_prepare_settings(base / "config" / "settings.json")
        schema_path = base / "config" / "config_schema.json"

        asset = next(
            (candidate for candidate in item.assets.values() if "data" in (candidate.roles or [])),
            None,
        )
        if asset is None:
            raise CompositorError("No data asset found in Harmony item.")

        local_in = download(
            asset.href,
            Path(settings["data_dir"]),
            logger=self.logger,
            access_token=self.message.accessToken,
        )

        # Harmony downloads can prepend a numeric token.  Recovering the source
        # filename keeps output names stable and matches the Filtering Service.
        parsed = urlparse(asset.href)
        original_name = Path(unquote(parsed.path)).name
        clean_name = re.sub(r"^\d+_", "", original_name)
        staged_input = Path(settings["data_dir"]) / clean_name
        if Path(local_in).resolve() != staged_input.resolve():
            shutil.move(local_in, staged_input)

        try:
            config, config_url = get_compositor_config_from_source(
                source,
                schema_path,
                requested_variable=requested_variable,
            )
            self.logger.info("Compositor configuration URL: %s", config_url)
            output_file = process_product(settings, config, clean_name)
        except CompositorError as exc:
            self.logger.error(str(exc))
            raise

        url = stage(
            output_file,
            output_file.name,
            "application/x-netcdf",
            location=self.message.stagingLocation,
            logger=self.logger,
        )
        result.assets["data"] = Asset(
            href=url,
            title=output_file.name,
            media_type="application/x-netcdf",
            roles=["data"],
        )
        return result


def main() -> None:
    """Run the service through harmony-service-lib's standard CLI wrapper."""
    parser = argparse.ArgumentParser(
        prog="compositor", description="Run the Harmony Compositor Service"
    )
    harmony_service_lib.setup_cli(parser)
    args = parser.parse_args()
    if harmony_service_lib.is_harmony_cli(args):
        harmony_service_lib.run_cli(parser, args, CompositorAdapter)
    else:
        parser.error("Only --harmony CLIs are supported by the service adapter.")


if __name__ == "__main__":
    main()
