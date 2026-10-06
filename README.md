# Harmony Compositor Service

Configuration-driven Harmony service for composing multiple source bands into a
single multi-channel output.  The initial implementation is intentionally
focused on **MISR DHR natural color** and is designed to be locally validated
with UAT data before additional products are introduced.

The repository follows the current Harmony Filtering Service conventions for
project layout, external configuration discovery, JSON-schema validation,
Docker packaging, GitHub workflows, and test organization.

## Initial scope

The first supported recipe reads:

`/Land_Parameter_Average/DHR`

and selects bands by their **Band coordinate labels**, not hard-coded numeric
indices:

- red: `red_672nm`
- green: `green_558nm`
- blue: `blue_446nm`

The selected channels are clipped to `[0, 1]`, source `-9999` values are treated
as nodata, and the values are display-scaled to `[0, 255]`. The output preserves
the complete input granule hierarchy and replaces only
`/Land_Parameter_Average/DHR` with a three-channel `rgb_band` composite ordered
red, green, blue. The original MISR `Band=4` dimension is left intact for other
variables that may still depend on it.

## External configuration metadata

Compositor configuration is not mapped to collections in source code.  Harmony
finds the externally hosted JSON configuration from the requested UMM-Var
RelatedURL using exactly:

```text
DistributionURL
  > SERVICE CONFIGURATION
    > COMPOSITOR CONFIGURATION
```

This is deliberately separate from the Filtering Service metadata subtype:

```text
DistributionURL
  > SERVICE CONFIGURATION
    > FILTERING CONFIGURATION
```

The sample file intended for MISR configuration hosting is:

`examples/misr_dhr_natural_color_compositor_config.json`

The configuration is validated against `config/config_schema.json` before any
science processing starts.  Invalid/missing configuration and missing
variables/bands return explicit errors.

## Repository layout

```text
harmony-compositor-service/
├── config/
│   ├── config_schema.json
│   ├── misr_dhr_natural_color_compositor_config.json
│   ├── settings.json
│   └── settings_schema.json
├── docker/
│   ├── docker-entrypoint.sh
│   ├── service.Dockerfile
│   ├── service_version.txt
│   └── tests.Dockerfile
├── docs/
│   └── misr_compositor_demo.ipynb
├── scripts/
│   └── run_local_misr.sh
├── src/harmony_compositor_service/
│   ├── adapter.py
│   ├── adapter_utils.py
│   ├── cli.py
│   ├── config_utility.py
│   ├── config_validator.py
│   ├── core.py
│   └── exceptions.py
├── tests/
├── utils/
│   └── granule_downloader.py
├── pyproject.toml
└── README.md
```

## Development setup

Python 3.12 and `uv` are used to match the Filtering Service baseline.

```bash
uv sync --extra dev
uv run pytest -m "not integration"
uv run ruff check src tests
```

## Local MISR test

Once a representative MISR UAT granule is available locally:

```bash
./scripts/run_local_misr.sh /path/to/MISR_UAT_granule.nc
```

or run the CLI directly:

```bash
uv run python -m harmony_compositor_service.cli \
  --input /path/to/MISR_UAT_granule.nc \
  --config examples/misr_dhr_natural_color_compositor_config.json
```

Successful output is written to:

```text
data/out_data/<input-stem>_composited.nc
```

A useful verification command is:

```python
import xarray as xr

ds = xr.open_dataset(
    "data/out_data/<input-stem>_composited.nc",
    group="Land_Parameter_Average",
    engine="netcdf4",
)
print(ds["DHR"])
print(ds["rgb_band"].values)
```

Expected DHR shape is `(Latitude, Longitude, rgb_band)` with `rgb_band=3` and channel order `['red', 'green', 'blue']`.

## Harmony runtime flow

1. Harmony invokes `CompositorAdapter` for an input STAC item.
2. The adapter finds the data asset and downloads it using
   `harmony-service-lib`.
3. The requested source variable's UMM-Var RelatedURL is searched for
   `COMPOSITOR CONFIGURATION`.
4. The external JSON is downloaded and validated against the schema.
5. The configured source variable and Band coordinate labels are validated.
6. The configured channels are selected, clipped, and display-scaled.
7. The full source NetCDF hierarchy is copied and only the configured target
   variable is replaced at the same path with a three-channel RGB composite.
8. The output is staged to Harmony and returned as the item's `data` asset.

## Configuration design

The implementation intentionally separates **generic capabilities** from
**product recipes**.

Generic service code handles:

- remote configuration discovery and validation;
- grouped netCDF variable paths;
- coordinate-value band selection;
- nodata handling;
- clipping;
- channel stacking and display scaling;
- recursive NetCDF group/variable/attribute preservation;
- target-variable replacement at the original grouped path;
- CF/grid-mapping preservation;
- Harmony download/stage behavior.

The MISR JSON supplies product-specific information such as the DHR path, Band
labels, clip range, channel order, and output naming.  This keeps MISR-specific
band knowledge out of the Python processing code.

## Docker

Build the service image:

```bash
./bin/build-image
```

Build and run the unit-test image:

```bash
./bin/run-test
```

## Configuration hosting / UMM-Var curation

Before a Harmony UAT test, host
`misr_dhr_natural_color_compositor_config.json` at the approved configuration
location and add that URL to the appropriate MISR UMM-Var RelatedURL using:

```text
URL Content Type: DistributionURL
Type:             SERVICE CONFIGURATION
Subtype:          COMPOSITOR CONFIGURATION
```

The service intentionally does not contain a fallback hard-coded configuration
URL.  Missing curation should fail clearly rather than silently applying the
wrong recipe.

## Current limitations

- Initial science support is MISR DHR natural-color composition only.
- OPERA and NISAR are intentionally out of scope for this first implementation.
- UAT credentials/test granules are not committed to the repository.
- The MISR output contract is a preserved granule with
  `/Land_Parameter_Average/DHR(Latitude, Longitude, rgb_band=3)`.
- Net2Cog/HyBIG end-to-end behavior still requires local and Harmony UAT
  validation with representative MISR granules.
