from __future__ import annotations

import numpy as np
import pytest
import xarray as xr

from harmony_compositor_service.core import compose_granule

netCDF4 = pytest.importorskip("netCDF4")


def test_grouped_misr_style_variable_is_composed(tmp_path):
    """Exercise the grouped-variable path used by the real MISR recipe."""
    values = np.zeros((2, 2, 4), dtype=np.float32)
    values[:, :, 0] = 0.1
    values[:, :, 1] = 0.2
    values[:, :, 2] = 0.3
    values[:, :, 3] = 0.4

    ds = xr.Dataset(
        {
            "DHR": xr.DataArray(
                values,
                dims=("y", "x", "Band"),
                coords={
                    "Band": ["blue_446nm", "green_558nm", "red_672nm", "nir_867nm"]
                },
                attrs={"grid_mapping": "crs"},
            ),
            "crs": xr.DataArray(0, attrs={"spatial_ref": "synthetic"}),
        }
    )
    source = tmp_path / "misr.nc"
    ds.to_netcdf(source, group="Land_Parameter_Average", engine="netcdf4")

    config = {
        "metadata": {
            "mission": "MISR",
            "name": "MISR DHR Natural Color",
            "config_type": "compositor",
            "schema_version": "1.0",
        },
        "input": {
            "variable": "/Land_Parameter_Average/DHR",
            "band_dimension": "Band",
            "band_coordinate": "Band",
        },
        "channels": [
            {"name": "red", "select": {"value": "red_672nm"}},
            {"name": "green", "select": {"value": "green_558nm"}},
            {"name": "blue", "select": {"value": "blue_446nm"}},
        ],
        "processing": {"clip": {"min": 0.0, "max": 1.0}, "nodata_values": [-9999.0]},
        "output": {
            "variable": "rgb",
            "channel_dimension": "rgb_band",
            "channel_order": ["red", "green", "blue"],
            "dtype": "float32",
            "fill_value": -9999.0,
        },
    }

    target = tmp_path / "out.nc"
    compose_granule(source, config, target)

    with xr.open_dataset(target, engine="netcdf4") as out:
        assert list(out.rgb_band.values) == ["red", "green", "blue"]
        np.testing.assert_allclose(out.rgb.sel(rgb_band="red"), 0.3)
        assert "crs" in out.variables
