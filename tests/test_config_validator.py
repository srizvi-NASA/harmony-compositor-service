import json
from pathlib import Path

import pytest

from harmony_compositor_service.config_validator import load_and_validate_config
from harmony_compositor_service.exceptions import ConfigurationError

ROOT = Path(__file__).parents[1]
SCHEMA = ROOT / "config" / "config_schema.json"
CONFIG = ROOT / "examples" / "misr_dhr_natural_color_compositor_config.json"


def test_sample_misr_config_is_valid():
    config = load_and_validate_config(CONFIG, SCHEMA)
    assert config["metadata"]["config_type"] == "compositor"
    assert config["input"]["variable"] == "/Land_Parameter_Average/DHR"
    assert config["output"]["variable"] == "/Land_Parameter_Average/DHR"
    assert config["output"]["preserve_structure"] is True
    assert config["output"]["channel_order"] == ["red", "green", "blue"]
    assert config["output"]["display_range"] == {"min": 0.0, "max": 255.0}


def test_invalid_config_reports_location(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text('{"metadata": {"mission": "MISR"}}', encoding="utf-8")
    with pytest.raises(ConfigurationError, match="Configuration validation error"):
        load_and_validate_config(bad, SCHEMA)


def test_clip_min_must_be_less_than_max(tmp_path):
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    config["processing"]["clip"] = {"min": 1.0, "max": 1.0}
    path = tmp_path / "bad_clip.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(ConfigurationError, match="min must be < max"):
        load_and_validate_config(path, SCHEMA)


def test_channel_order_must_match_defined_channels(tmp_path):
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    config["output"]["channel_order"] = ["red", "green", "nir"]
    path = tmp_path / "bad_order.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(ConfigurationError, match="match the configured channel names"):
        load_and_validate_config(path, SCHEMA)


def test_output_variable_must_match_input_variable(tmp_path):
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    config["output"]["variable"] = "/RGB"
    path = tmp_path / "bad_output.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(ConfigurationError, match="must match input.variable"):
        load_and_validate_config(path, SCHEMA)


def test_channel_dimension_must_not_reuse_source_band_dimension(tmp_path):
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    config["output"]["channel_dimension"] = "Band"
    path = tmp_path / "bad_dimension.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(ConfigurationError, match="use a new dimension name"):
        load_and_validate_config(path, SCHEMA)
