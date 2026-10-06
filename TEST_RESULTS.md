# Test Results

Validation performed for the structure-preserving MISR RGB update:

- `PYTHONPATH=src pytest -q` -> **15 passed, 1 skipped**.
- The skipped test is the grouped netCDF4 integration test because the artifact
  environment does not provide the `netCDF4` Python package.
- `python -m compileall -q src tests` passed.
- `uv lock --check` passed.
- Full `uv sync --extra dev --frozen` could not be completed in the artifact
  environment because external package downloads were blocked by DNS/network
  restrictions.

The Docker/runtime dependency list already includes `netCDF4`; the grouped
structure-preservation test is intended to run in the normal project test image
and local development environment.
