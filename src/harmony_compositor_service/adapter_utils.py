"""Small helpers shared by the Harmony adapter and local CLI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, cast


def load_and_prepare_settings(path: Path) -> Dict[str, Any]:
    """Load service settings and resolve working directories to absolute paths."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    settings: Dict[str, Any] = cast(Dict[str, Any], raw)

    for key in ("data_dir", "output_dir"):
        directory = Path(settings[key]).expanduser().resolve()
        directory.mkdir(parents=True, exist_ok=True)
        settings[key] = str(directory)

    return settings
