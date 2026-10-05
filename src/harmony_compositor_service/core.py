"""Core, configuration-driven composition logic.

The core module deliberately contains no Harmony-specific code.  It accepts a
local netCDF granule and a validated configuration, then writes a composited
netCDF output.  Keeping Harmony I/O in ``adapter.py`` makes the science logic
straightforward to unit-test with small synthetic files.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import xarray as xr

from harmony_compositor_service.exceptions import GranuleProcessingError


def split_variable_path(variable_path: str) -> tuple[str | None, str]:
    """Split an absolute/grouped netCDF variable path into group and variable.

    Examples
    --------
    ``/Land_Parameter_Average/DHR`` becomes
    ``("Land_Parameter_Average", "DHR")``.  A root variable such as ``DHR``
    becomes ``(None, "DHR")``.
    """
    cleaned = variable_path.strip().strip("/")
    if not cleaned:
        raise GranuleProcessingError("Configured input variable path is empty.")

    parts = cleaned.split("/")
    if len(parts) == 1:
        return None, parts[0]
    return "/".join(parts[:-1]), parts[-1]


def _decode_label(value: Any) -> Any:
    """Decode byte-valued netCDF coordinates so JSON string labels compare cleanly."""
    if isinstance(value, bytes):
        return value.decode("utf-8")
    if isinstance(value, np.bytes_):
        return value.tobytes().decode("utf-8")
    return value


def _coordinate_values(data: xr.DataArray, coordinate_name: str) -> list[Any]:
    """Return normalized coordinate labels used for config-driven selection."""
    if coordinate_name not in data.coords:
        raise GranuleProcessingError(
            f"Configured band coordinate '{coordinate_name}' was not found for "
            f"variable '{data.name}'."
        )
    values = data.coords[coordinate_name].values
    return [_decode_label(value) for value in np.asarray(values).tolist()]


def _select_channel(
    data: xr.DataArray,
    *,
    band_dimension: str,
    band_coordinate: str,
    selected_value: Any,
    channel_name: str,
) -> xr.DataArray:
    """Select one configured band by its coordinate value, never by hard-coded index."""
    if band_dimension not in data.dims:
        raise GranuleProcessingError(
            f"Configured band dimension '{band_dimension}' was not found in "
            f"variable '{data.name}'. Available dimensions: {data.dims}."
        )

    available = _coordinate_values(data, band_coordinate)
    requested = _decode_label(selected_value)
    if requested not in available:
        raise GranuleProcessingError(
            f"Band '{requested}' configured for channel '{channel_name}' was not found. "
            f"Available '{band_coordinate}' values: {available}."
        )

    # Use the matched position rather than xarray.sel because some netCDF files
    # expose a dimension-scale coordinate whose decoded dtype differs from the
    # JSON scalar (for example bytes vs. str).  The index is *derived* from the
    # coordinate value and is therefore not product-hardcoded.
    index = available.index(requested)
    selected = data.isel({band_dimension: index}, drop=True)
    selected.name = channel_name
    return selected


def _apply_processing(data: xr.DataArray, config: dict[str, Any]) -> xr.DataArray:
    """Apply common nodata and clipping rules to a selected channel."""
    result = data.astype(np.float64)

    # Preserve existing NaNs and translate explicitly configured source nodata
    # values into NaN before clipping.  This prevents source fill values such as
    # -9999 from being clipped into a plausible display value of 0.
    for nodata_value in config["processing"].get("nodata_values", []):
        result = result.where(result != float(nodata_value))

    clip = config["processing"]["clip"]
    result = result.clip(min=float(clip["min"]), max=float(clip["max"]))
    return result


def _copy_support_variables(
    source_path: Path,
    group: str | None,
    source_data: xr.DataArray,
    output: xr.Dataset,
) -> xr.Dataset:
    """Copy small geospatial support variables referenced by the source variable.

    A CF ``grid_mapping`` variable (commonly named ``crs``) is essential for
    downstream geospatial services.  It is copied when present in the same
    group.  Dimension coordinates are already carried by xarray during concat.
    """
    grid_mapping = source_data.attrs.get("grid_mapping")
    if not grid_mapping:
        return output

    try:
        with xr.open_dataset(source_path, group=group, decode_cf=False) as source_ds:
            if grid_mapping in source_ds.variables:
                output[grid_mapping] = source_ds[grid_mapping].load()
    except (OSError, ValueError):
        # Failure to copy an optional support variable should not hide a valid
        # composition.  The primary variable's attributes remain available for
        # diagnostics and validation by downstream services.
        pass
    return output


def compose_granule(
    input_path: str | Path,
    config: dict[str, Any],
    output_path: str | Path,
) -> Path:
    """Compose configured source bands and write a single multi-channel netCDF.

    The output contains one variable (``rgb`` in the MISR recipe) whose final
    dimension is the configured channel dimension.  Channel labels are written
    as a coordinate, so downstream processing can discover the R/G/B order
    without relying on implicit numeric indices.
    """
    input_path = Path(input_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    group, variable_name = split_variable_path(config["input"]["variable"])
    band_dimension = config["input"]["band_dimension"]
    band_coordinate = config["input"].get("band_coordinate", band_dimension)

    try:
        with xr.open_dataset(input_path, group=group, decode_cf=True) as dataset:
            if variable_name not in dataset.variables:
                group_text = group or "/"
                raise GranuleProcessingError(
                    f"Configured variable '{variable_name}' was not found in group "
                    f"'{group_text}'."
                )

            source = dataset[variable_name]
            source_attrs = dict(source.attrs)
            root_attrs = dict(dataset.attrs)

            channels: dict[str, xr.DataArray] = {}
            for channel in config["channels"]:
                name = channel["name"]
                selected = _select_channel(
                    source,
                    band_dimension=band_dimension,
                    band_coordinate=band_coordinate,
                    selected_value=channel["select"]["value"],
                    channel_name=name,
                )
                channels[name] = _apply_processing(selected, config).load()

            order = config["output"]["channel_order"]
            missing = [name for name in order if name not in channels]
            if missing:
                raise GranuleProcessingError(
                    f"Output channel_order references undefined channels: {missing}."
                )

            output_dimension = config["output"]["channel_dimension"]
            stacked = xr.concat(
                [channels[name] for name in order],
                dim=xr.IndexVariable(output_dimension, order),
            )

            # Keep the spatial dimensions first and RGB/channel dimension last.
            spatial_dims = [dim for dim in stacked.dims if dim != output_dimension]
            stacked = stacked.transpose(*spatial_dims, output_dimension)
            stacked.name = config["output"]["variable"]
            stacked.attrs = {
                key: value
                for key, value in source_attrs.items()
                if key not in {"_FillValue", "valid_min", "valid_max"}
            }
            stacked.attrs.update(
                {
                    "long_name": config["metadata"]["name"],
                    "compositor_config_schema_version": config["metadata"]["schema_version"],
                    "compositor_channel_order": ",".join(order),
                }
            )

            output = xr.Dataset({stacked.name: stacked}, attrs=root_attrs)
            output.attrs.update(
                {
                    "compositor_service": "Harmony Compositor Service",
                    "compositor_config_name": config["metadata"]["name"],
                }
            )
            output = _copy_support_variables(input_path, group, source, output)

        fill_value = float(config["output"]["fill_value"])
        dtype = config["output"]["dtype"]
        encoding: dict[str, Any] = {
            config["output"]["variable"]: {
                "dtype": dtype,
                "_FillValue": fill_value,
            }
        }

        # netCDF4 is a runtime dependency of the service and supports grouped
        # source products plus compression.  The fallback keeps lightweight
        # developer/test environments usable when only scipy is installed.
        try:
            import netCDF4  # noqa: F401

            encoding[config["output"]["variable"]].update(
                {"zlib": True, "complevel": 4, "shuffle": True}
            )
            output.to_netcdf(
                output_path, mode="w", engine="netcdf4", encoding=encoding
            )
        except ImportError:  # pragma: no cover - CI/runtime installs netCDF4
            output.to_netcdf(output_path, mode="w", engine="scipy", encoding=encoding)
    except GranuleProcessingError:
        raise
    except Exception as exc:
        raise GranuleProcessingError(
            f"Failed to compose granule '{input_path.name}': {exc}"
        ) from exc

    return output_path


def process_product(
    settings: dict[str, Any],
    config: dict[str, Any],
    input_filename: str,
) -> Path:
    """Process one file staged in ``settings['data_dir']`` and return its output."""
    input_path = Path(settings["data_dir"]) / input_filename
    if not input_path.exists():
        raise GranuleProcessingError(f"Input granule does not exist: {input_path}")

    output_dir = Path(settings["output_dir"])
    output_path = output_dir / f"{input_path.stem}_composited.nc"
    return compose_granule(input_path, config, output_path)
