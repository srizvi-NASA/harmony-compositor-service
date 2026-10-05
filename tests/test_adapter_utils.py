import json
from pathlib import Path

from harmony_compositor_service.adapter_utils import load_and_prepare_settings


def test_load_and_prepare_settings_creates_directories(tmp_path):
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(
        json.dumps(
            {
                "data_dir": str(tmp_path / "input"),
                "output_dir": str(tmp_path / "output"),
                "logging": {},
                "test": {},
            }
        ),
        encoding="utf-8",
    )
    settings = load_and_prepare_settings(settings_file)
    assert Path(settings["data_dir"]).is_dir()
    assert Path(settings["output_dir"]).is_dir()
