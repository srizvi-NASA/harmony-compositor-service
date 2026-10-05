# Contributing

This repository follows the same development conventions as the Harmony
Filtering Service baseline.

Before opening a pull request:

```bash
uv sync --extra dev
uv run ruff check src tests
uv run pytest -m "not integration"
```

Keep product-specific rules in external JSON configuration whenever practical.
Python code should implement reusable capabilities rather than MISR-specific
band indices or collection-to-configuration mappings.

New configuration fields require:

1. an update to `config/config_schema.json`;
2. unit tests for valid and invalid cases;
3. README documentation; and
4. backward-compatibility consideration for already curated configurations.

Comments should explain *why* non-obvious logic exists.  Public functions and
modules should have docstrings.  Do not commit credentials, downloaded science
granules, generated outputs, or local virtual environments.
