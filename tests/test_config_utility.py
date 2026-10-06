from pathlib import Path
from unittest.mock import Mock

import pytest

from harmony_compositor_service.config_utility import (
    get_compositor_config_url,
    get_remote_compositor_config,
)
from harmony_compositor_service.exceptions import ConfigurationError

ROOT = Path(__file__).parents[1]
SCHEMA = ROOT / "config" / "config_schema.json"


def _source(subtype="COMPOSITOR CONFIGURATION"):
    return {
        "variables": [
            {
                "name": "/Land_Parameter_Average/DHR",
                "relatedUrls": [
                    {
                        "urlContentType": "DistributionURL",
                        "type": "SERVICE CONFIGURATION",
                        "subtype": subtype,
                        "url": "https://example.test/misr-compositor.json",
                    }
                ],
            }
        ]
    }


def test_get_compositor_config_url_uses_compositor_subtype():
    assert get_compositor_config_url(_source()) == "https://example.test/misr-compositor.json"


def test_filtering_subtype_is_not_accepted():
    with pytest.raises(ConfigurationError, match="COMPOSITOR CONFIGURATION"):
        get_compositor_config_url(_source("FILTERING CONFIGURATION"))


def test_remote_config_is_schema_validated(monkeypatch):
    sample = {
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
        "processing": {"clip": {"min": 0, "max": 1}, "nodata_values": [-9999]},
        "output": {
            "variable": "/Land_Parameter_Average/DHR",
            "preserve_structure": True,
            "channel_dimension": "rgb_band",
            "channel_order": ["red", "green", "blue"],
            "display_range": {"min": 0, "max": 255},
            "dtype": "float32",
            "fill_value": -9999,
        },
    }
    response = Mock(ok=True)
    response.json.return_value = sample
    monkeypatch.setattr(
        "harmony_compositor_service.config_utility.requests.get",
        lambda *a, **k: response,
    )
    assert get_remote_compositor_config("https://example.test/config.json", SCHEMA) == sample
