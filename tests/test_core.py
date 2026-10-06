import numpy as np
import pytest
import xarray as xr

from harmony_compositor_service.core import (
    _apply_processing,
    _scale_for_display,
    _select_channel,
    split_variable_path,
)
from harmony_compositor_service.exceptions import GranuleProcessingError


def _config():
    return {
        "metadata": {
            "mission": "MISR",
            "name": "Synthetic MISR RGB",
            "config_type": "compositor",
            "schema_version": "1.1",
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
            "variable": "/Land_Parameter_Average/DHR",
            "preserve_structure": True,
            "channel_dimension": "rgb_band",
            "channel_order": ["red", "green", "blue"],
            "display_range": {"min": 0.0, "max": 255.0},
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


def test_scale_for_display_maps_zero_one_to_zero_255():
    data = xr.DataArray([[0.0, 0.25, 0.5, 1.0, np.nan]])
    result = _scale_for_display(data, _config())
    np.testing.assert_allclose(result.values[0, :4], [0.0, 63.75, 127.5, 255.0])
    assert np.isnan(result.values[0, 4])
