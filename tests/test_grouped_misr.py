from __future__ import annotations

import numpy as np
import pytest
import xarray as xr

from harmony_compositor_service.core import compose_granule

netCDF4 = pytest.importorskip("netCDF4")


def _config():
    return {
        "metadata": {
            "mission": "MISR",
            "name": "MISR DHR Natural Color",
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


def test_grouped_misr_structure_is_preserved_and_dhr_is_replaced(tmp_path):
    source = tmp_path / "misr.nc"
    target = tmp_path / "out.nc"

    with netCDF4.Dataset(source, "w", format="NETCDF4") as root:
        root.setncattr("title", "Synthetic MISR granule")

        info = root.createGroup("HDFEOS_INFORMATION")
        info.createDimension("n", 2)
        info_var = info.createVariable("coremetadata", "i4", ("n",))
        info_var[:] = [11, 22]

        group = root.createGroup("Land_Parameter_Average")
        group.setncattr("group_note", "preserve me")
        group.createDimension("Latitude", 2)
        group.createDimension("Longitude", 3)
        group.createDimension("Band", 4)

        lat = group.createVariable("Latitude", "f4", ("Latitude",))
        lon = group.createVariable("Longitude", "f4", ("Longitude",))
        band = group.createVariable("Band", str, ("Band",))
        lat[:] = [1.0, 0.0]
        lon[:] = [10.0, 11.0, 12.0]
        band[:] = np.array(
            ["blue_446nm", "green_558nm", "red_672nm", "nir_867nm"], dtype=object
        )

        crs = group.createVariable("crs", "i4")
        crs.setncattr("spatial_ref", "synthetic")

        dhr = group.createVariable(
            "DHR", "f4", ("Latitude", "Longitude", "Band"), fill_value=-9999.0
        )
        dhr.setncattr("grid_mapping", "crs")
        dhr.setncattr("units", "1")
        dhr.setncattr("valid_min", 0.0)
        dhr.setncattr("valid_max", 1.0)
        values = np.zeros((2, 3, 4), dtype=np.float32)
        values[:, :, 0] = 0.2
        values[:, :, 1] = 0.4
        values[:, :, 2] = 0.6
        values[:, :, 3] = 0.8
        values[1, 2, 0] = -9999.0
        dhr[:] = values

        # This variable deliberately continues to use the original Band=4
        # dimension, proving the Compositor does not shrink or repurpose it.
        other = group.createVariable("Other_Banded", "f4", ("Band",))
        other[:] = [1.0, 2.0, 3.0, 4.0]

        source_file = root.createGroup("Source_file")
        source_file.createDimension("Index", 1)
        source_index = source_file.createVariable("Index", "i4", ("Index",))
        source_index[:] = [7]

    compose_granule(source, _config(), target)

    with netCDF4.Dataset(target, "r") as root:
        assert root.getncattr("title") == "Synthetic MISR granule"
        assert "HDFEOS_INFORMATION" in root.groups
        np.testing.assert_array_equal(root["HDFEOS_INFORMATION/coremetadata"][:], [11, 22])
        assert "Source_file" in root.groups
        np.testing.assert_array_equal(root["Source_file/Index"][:], [7])

        group = root.groups["Land_Parameter_Average"]
        assert group.getncattr("group_note") == "preserve me"
        assert len(group.dimensions["Band"]) == 4
        assert len(group.dimensions["rgb_band"]) == 3
        np.testing.assert_allclose(group.variables["Other_Banded"][:], [1, 2, 3, 4])

        dhr = group.variables["DHR"]
        assert dhr.dimensions == ("Latitude", "Longitude", "rgb_band")
        assert dhr.shape == (2, 3, 3)
        assert dhr.dtype == np.dtype("float32")
        assert dhr.getncattr("grid_mapping") == "crs"
        assert "valid_min" not in dhr.ncattrs()
        assert "valid_max" not in dhr.ncattrs()

        np.testing.assert_allclose(dhr[:, :, 0], 153.0)  # red: 0.6 * 255
        np.testing.assert_allclose(dhr[:, :, 1], 102.0)  # green: 0.4 * 255
        assert dhr[0, 0, 2] == pytest.approx(51.0)       # blue: 0.2 * 255
        assert np.ma.is_masked(dhr[1, 2, 2])             # source blue nodata preserved

        rgb_band = group.variables["rgb_band"]
        np.testing.assert_array_equal(rgb_band[:], [1, 2, 3])
        assert rgb_band.getncattr("channel_names") == "red,green,blue"
