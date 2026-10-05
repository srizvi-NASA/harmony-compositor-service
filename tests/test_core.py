from pathlib import Path

import numpy as np
import pytest
import xarray as xr

from harmony_compositor_service.core import (
    _apply_processing,
    _select_channel,
    compose_granule,
    split_variable_path,
)
from harmony_compositor_service.exceptions import GranuleProcessingError


def _config():
    return {
        "metadata": {
            "mission": "MISR",
            "name": "Synthetic MISR RGB",
            "config_type": "compositor",
            "schema_version": "1.0",
        },
        "input": {
            "variable": "/DHR",
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


def test_split_variable_path():
    assert split_variable_path("/Land_Parameter_Average/DHR") == ("Land_Parameter_Average", "DHR")
    assert split_variable_path("DHR") == (None, "DHR")


def test_select_channel_uses_coordinate_label():
    data = xr.DataArray(
        np.arange(12).reshape(2, 2, 3),
        dims=("y", "x", "Band"),
        coords={"Band": ["blue_446nm", "green_558nm", "red_672nm"]},
        name="DHR",
    )
    red = _select_channel(
        data,
        band_dimension="Band",
        band_coordinate="Band",
        selected_value="red_672nm",
        channel_name="red",
    )
    np.testing.assert_array_equal(red.values, data.isel(Band=2).values)


def test_missing_band_has_clear_error():
    data = xr.DataArray(
        np.zeros((1, 1, 1)),
        dims=("y", "x", "Band"),
        coords={"Band": ["blue_446nm"]},
        name="DHR",
    )
    with pytest.raises(GranuleProcessingError, match="Available 'Band' values"):
        _select_channel(
            data,
            band_dimension="Band",
            band_coordinate="Band",
            selected_value="red_672nm",
            channel_name="red",
        )


def test_processing_preserves_nodata_and_clips():
    data = xr.DataArray([[-9999.0, -0.1, 0.5, 1.2]])
    result = _apply_processing(data, _config())
    assert np.isnan(result.values[0, 0])
    np.testing.assert_allclose(result.values[0, 1:], [0.0, 0.5, 1.0])


def test_compose_granule_end_to_end_with_root_synthetic_file(tmp_path):
    values = np.zeros((2, 3, 4), dtype=np.float32)
    values[:, :, 0] = 0.2  # blue
    values[:, :, 1] = 0.4  # green
    values[:, :, 2] = 0.6  # red
    values[:, :, 3] = 0.8  # NIR (not selected)
    values[0, 0, 2] = 1.5  # red should clip to 1
    values[1, 2, 0] = -9999.0  # blue should remain fill/nodata

    ds = xr.Dataset(
        {
            "DHR": xr.DataArray(
                values,
                dims=("y", "x", "Band"),
                coords={
                    "y": [1.0, 0.0],
                    "x": [10.0, 11.0, 12.0],
                    "Band": ["blue_446nm", "green_558nm", "red_672nm", "nir_867nm"],
                },
                attrs={"units": "1"},
            )
        }
    )
    source = tmp_path / "input.nc"
    target = tmp_path / "output.nc"
    ds.to_netcdf(source, engine="scipy")

    compose_granule(source, _config(), target)
    with xr.open_dataset(target) as output:
        assert output["rgb"].dims == ("y", "x", "rgb_band")
        assert list(output["rgb_band"].values) == ["red", "green", "blue"]
        assert output["rgb"].shape == (2, 3, 3)
        assert output["rgb"].sel(rgb_band="red").values[0, 0] == pytest.approx(1.0)
        assert np.isnan(output["rgb"].sel(rgb_band="blue").values[1, 2])
