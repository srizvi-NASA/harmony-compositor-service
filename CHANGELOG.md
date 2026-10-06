## Unreleased

- Preserve the full input NetCDF hierarchy during composition.
- Replace the configured target variable at its original grouped path instead of creating a root-level RGB variable.
- Emit MISR DHR as a three-channel `rgb_band` composite while retaining the original `Band=4` dimension for unrelated variables.
- Scale configured clipped values into a display-ready range (MISR: 0..1 to 0..255) for Net2Cog/HyBIG compatibility.
- Add structure-preservation and output-contract validation/tests.

# Changelog

## 0.1.0 - Initial development

- Added Harmony-compatible Compositor adapter modeled on the working Filtering Service.
- Added external UMM-Var configuration discovery using `COMPOSITOR CONFIGURATION`.
- Added JSON schema and provisional MISR DHR natural-color configuration.
- Added coordinate-label-driven MISR band selection and RGB channel stacking.
- Added nodata handling, clipping, output metadata, and netCDF staging support.
- Added unit tests, Docker files, CI workflow scaffolding, local test script, and demo notebook.
