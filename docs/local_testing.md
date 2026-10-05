# Local testing with MISR UAT data

1. Obtain a representative MISR UAT granule using the same Earthdata UAT
   credentials/environment used for Harmony development.
2. Confirm the granule contains `/Land_Parameter_Average/DHR` and that the
   `Band` coordinate includes `red_672nm`, `green_558nm`, and `blue_446nm`.
3. Install the repository dependencies with `uv sync --extra dev`.
4. Run:

```bash
./scripts/run_local_misr.sh /path/to/granule.nc
```

5. Inspect the resulting `*_composited.nc` file in `data/out_data`.

Expected checks:

- output variable is `rgb`;
- channel coordinate is `rgb_band`;
- order is red, green, blue;
- output spatial dimensions match the DHR spatial dimensions;
- configured source nodata is represented as output fill/nodata;
- values are in the configured `[0, 1]` range;
- CF/grid-mapping metadata required by downstream processing is retained.

After local validation, host the JSON configuration and curate its UMM-Var
RelatedURL with subtype `COMPOSITOR CONFIGURATION`, then exercise the Harmony
service path in UAT.
