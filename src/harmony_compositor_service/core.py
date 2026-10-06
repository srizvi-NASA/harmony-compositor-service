"""Core, configuration-driven composition logic.

The core module deliberately contains no Harmony-specific code. It accepts a
local netCDF granule and a validated configuration, then writes a composited
netCDF output while preserving the input granule hierarchy. For MISR, only the
configured target variable is replaced; all unrelated groups, dimensions,
variables, and attributes are copied forward.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import xarray as xr

from harmony_compositor_service.exceptions import GranuleProcessingError


def split_variable_path(variable_path: str) -> tuple[str | None, str]:
    """Split an absolute/grouped netCDF variable path into group and variable."""
    cleaned = variable_path.strip().strip("/")
    if not cleaned:
        raise GranuleProcessingError("Configured input variable path is empty.")

    parts = cleaned.split("/")
    if len(parts) == 1:
        return None, parts[0]
    return "/".join(parts[:-1]), parts[-1]


def _canonical_variable_path(variable_path: str) -> str:
    """Return a normalized absolute variable path."""
    group, variable = split_variable_path(variable_path)
    return f"/{group}/{variable}" if group else f"/{variable}"


def _decode_label(value: Any) -> Any:
    """Decode byte-valued netCDF coordinates so JSON labels compare cleanly."""
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
    """Select one configured band by coordinate value, never hard-coded index."""
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

    index = available.index(requested)
    selected = data.isel({band_dimension: index}, drop=True)
    selected.name = channel_name
    return selected


def _apply_processing(data: xr.DataArray, config: dict[str, Any]) -> xr.DataArray:
    """Translate configured nodata to NaN and clip a selected source channel."""
    result = data.astype(np.float64)

    for nodata_value in config["processing"].get("nodata_values", []):
        result = result.where(result != float(nodata_value))

    clip = config["processing"]["clip"]
    return result.clip(min=float(clip["min"]), max=float(clip["max"]))


def _scale_for_display(data: xr.DataArray, config: dict[str, Any]) -> xr.DataArray:
    """Linearly scale clipped science values into the configured display range.

    MISR DHR is clipped to 0..1 and then scaled to 0..255. Keeping the output as
    floating point allows -9999 to remain an unambiguous nodata value while
    Net2Cog can emit three raster bands that HyBIG can consume as RGB.
    """
    clip = config["processing"]["clip"]
    display = config["output"]["display_range"]
    source_min = float(clip["min"])
    source_max = float(clip["max"])
    output_min = float(display["min"])
    output_max = float(display["max"])

    if source_max == source_min:
        raise GranuleProcessingError("Configured clip range cannot have zero width.")

    normalized = (data - source_min) / (source_max - source_min)
    return output_min + normalized * (output_max - output_min)


def _compose_target_data(
    input_path: Path, config: dict[str, Any]
) -> tuple[np.ndarray, dict[str, Any]]:
    """Create the replacement RGB data cube and return source variable metadata."""
    group, variable_name = split_variable_path(config["input"]["variable"])
    band_dimension = config["input"]["band_dimension"]
    band_coordinate = config["input"].get("band_coordinate", band_dimension)

    try:
        with xr.open_dataset(input_path, group=group, decode_cf=True, engine="netcdf4") as dataset:
            if variable_name not in dataset.variables:
                group_text = group or "/"
                raise GranuleProcessingError(
                    f"Configured variable '{variable_name}' was not found in group '{group_text}'."
                )

            source = dataset[variable_name]
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
                processed = _apply_processing(selected, config)
                channels[name] = _scale_for_display(processed, config).load()

            order = config["output"]["channel_order"]
            output_dimension = config["output"]["channel_dimension"]
            stacked = xr.concat(
                [channels[name] for name in order],
                dim=xr.IndexVariable(output_dimension, order),
            )

            output_dims = tuple(
                output_dimension if dim == band_dimension else dim for dim in source.dims
            )
            stacked = stacked.transpose(*output_dims)

            metadata = {
                "source_dimensions": tuple(source.dims),
                "source_attrs": dict(source.attrs),
                "output_dimensions": output_dims,
                "channel_labels": list(order),
                "source_band_values": [
                    channel["select"]["value"] for channel in config["channels"]
                ],
            }
            return np.asarray(stacked.values), metadata
    except GranuleProcessingError:
        raise
    except Exception as exc:
        raise GranuleProcessingError(
            f"Failed to compose variable '{config['input']['variable']}' from "
            f"granule '{input_path.name}': {exc}"
        ) from exc


def _get_fill_value(variable: Any) -> Any:
    """Return a netCDF variable's _FillValue, if present."""
    return variable.getncattr("_FillValue") if "_FillValue" in variable.ncattrs() else None


def _create_variable_like(dst_group: Any, name: str, source: Any) -> Any:
    """Create a destination variable preserving common netCDF storage settings."""
    filters = source.filters() or {}
    kwargs: dict[str, Any] = {}
    fill_value = _get_fill_value(source)
    if fill_value is not None:
        kwargs["fill_value"] = fill_value
    if filters.get("zlib", False):
        kwargs.update({"zlib": True, "shuffle": filters.get("shuffle", False)})
        if filters.get("complevel") is not None:
            kwargs["complevel"] = filters["complevel"]
    return dst_group.createVariable(name, source.datatype, source.dimensions, **kwargs)


def _copy_variable_attributes(source: Any, destination: Any, skip: set[str] | None = None) -> None:
    """Copy variable attributes except those explicitly skipped."""
    skipped = {"_FillValue"}
    if skip:
        skipped.update(skip)
    for attr in source.ncattrs():
        if attr not in skipped:
            destination.setncattr(attr, source.getncattr(attr))


def _copy_group_preserving_structure(
    src_group: Any,
    dst_group: Any,
    current_group: str,
    *,
    target_path: str,
    replacement_data: np.ndarray,
    replacement_metadata: dict[str, Any],
    config: dict[str, Any],
) -> None:
    """Recursively copy a netCDF group, replacing only the configured variable."""
    target_group, target_name = split_variable_path(target_path)
    target_group = target_group or ""

    for dim_name, dim in src_group.dimensions.items():
        dst_group.createDimension(dim_name, None if dim.isunlimited() else len(dim))

    is_target_group = current_group == target_group
    channel_dimension = config["output"]["channel_dimension"]
    if is_target_group and channel_dimension not in dst_group.dimensions:
        dst_group.createDimension(channel_dimension, len(config["output"]["channel_order"]))

    for var_name, source_var in src_group.variables.items():
        full_path = f"/{current_group}/{var_name}" if current_group else f"/{var_name}"
        if full_path == _canonical_variable_path(target_path):
            source_dims = list(source_var.dimensions)
            band_dimension = config["input"]["band_dimension"]
            if band_dimension not in source_dims:
                raise GranuleProcessingError(
                    f"Target variable '{full_path}' does not use configured band dimension "
                    f"'{band_dimension}'."
                )
            output_dims = tuple(
                channel_dimension if dim == band_dimension else dim
                for dim in source_dims
            )

            fill_value = config["output"]["fill_value"]
            dtype = config["output"]["dtype"]
            filters = source_var.filters() or {}
            kwargs: dict[str, Any] = {"fill_value": fill_value}
            if filters.get("zlib", False):
                kwargs.update({"zlib": True, "shuffle": filters.get("shuffle", False)})
                if filters.get("complevel") is not None:
                    kwargs["complevel"] = filters["complevel"]

            dst_var = dst_group.createVariable(var_name, dtype, output_dims, **kwargs)
            _copy_variable_attributes(
                source_var,
                dst_var,
                skip={
                    "valid_min",
                    "valid_max",
                    "valid_range",
                    "scale_factor",
                    "add_offset",
                    "_Unsigned",
                },
            )
            dst_var.setncattr("long_name", config["metadata"]["name"])
            dst_var.setncattr(
                "compositor_config_schema_version",
                config["metadata"]["schema_version"],
            )
            dst_var.setncattr(
                "compositor_channel_order",
                ",".join(config["output"]["channel_order"]),
            )
            dst_var.setncattr(
                "compositor_source_band_values",
                ",".join(str(value) for value in replacement_metadata["source_band_values"]),
            )
            display = config["output"]["display_range"]
            dst_var.setncattr("compositor_display_range", f"{display['min']},{display['max']}")

            data = np.asarray(replacement_data, dtype=dtype)
            data = np.where(np.isnan(data), fill_value, data)
            dst_var[:] = data
        else:
            dst_var = _create_variable_like(dst_group, var_name, source_var)
            _copy_variable_attributes(source_var, dst_var)
            dst_var[:] = source_var[:]

    if is_target_group and channel_dimension not in src_group.variables:
        coord = dst_group.createVariable(channel_dimension, "i2", (channel_dimension,))
        coord[:] = np.arange(1, len(config["output"]["channel_order"]) + 1, dtype=np.int16)
        coord.setncattr("long_name", "RGB channel index")
        coord.setncattr("channel_names", ",".join(config["output"]["channel_order"]))
        coord.setncattr(
            "source_band_values",
            ",".join(str(value) for value in replacement_metadata["source_band_values"]),
        )

    for attr in src_group.ncattrs():
        dst_group.setncattr(attr, src_group.getncattr(attr))

    if current_group == "":
        dst_group.setncattr("compositor_service", "Harmony Compositor Service")
        dst_group.setncattr("compositor_config_name", config["metadata"]["name"])

    for subgroup_name, subgroup in src_group.groups.items():
        new_group = dst_group.createGroup(subgroup_name)
        new_current = f"{current_group}/{subgroup_name}" if current_group else subgroup_name
        _copy_group_preserving_structure(
            subgroup,
            new_group,
            new_current,
            target_path=target_path,
            replacement_data=replacement_data,
            replacement_metadata=replacement_metadata,
            config=config,
        )


def compose_granule(
    input_path: str | Path,
    config: dict[str, Any],
    output_path: str | Path,
) -> Path:
    """Compose RGB and preserve the source granule hierarchy.

    The configured input variable is replaced at the same group/name with a
    three-channel composite. All other source groups, dimensions, variables,
    and attributes are copied into the output granule.
    """
    input_path = Path(input_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        import netCDF4
    except ImportError as exc:  # pragma: no cover - runtime dependency
        raise GranuleProcessingError(
            "netCDF4 is required for structure-preserving Compositor output."
        ) from exc

    target_path = _canonical_variable_path(config["input"]["variable"])
    output_target = _canonical_variable_path(config["output"]["variable"])
    if output_target != target_path:
        raise GranuleProcessingError(
            "For structure-preserving composition, output.variable must match input.variable."
        )

    replacement_data, replacement_metadata = _compose_target_data(input_path, config)

    try:
        with netCDF4.Dataset(input_path, "r") as source, netCDF4.Dataset(
            output_path, "w", format="NETCDF4"
        ) as destination:
            _copy_group_preserving_structure(
                source,
                destination,
                "",
                target_path=target_path,
                replacement_data=replacement_data,
                replacement_metadata=replacement_metadata,
                config=config,
            )
    except GranuleProcessingError:
        raise
    except Exception as exc:
        raise GranuleProcessingError(
            f"Failed to write structure-preserving composited granule '{input_path.name}': {exc}"
        ) from exc

    return output_path


def process_product(
    settings: dict[str, Any],
    config: dict[str, Any],
    input_filename: str,
) -> Path:
    """Process one staged granule and return the output path."""
    input_path = Path(settings["data_dir"]) / input_filename
    if not input_path.exists():
        raise GranuleProcessingError(f"Input granule does not exist: {input_path}")

    output_dir = Path(settings["output_dir"])
    output_path = output_dir / f"{input_path.stem}_composited.nc"
    return compose_granule(input_path, config, output_path)
