# Local testing with MISR UAT data

1. Obtain a representative MISR UAT granule.
2. Confirm it contains `/Land_Parameter_Average/DHR` and `Band` labels
   `red_672nm`, `green_558nm`, and `blue_446nm`.
3. Install dependencies with `uv sync --extra dev`.
4. Run:

```bash
./scripts/run_local_misr.sh /path/to/granule.nc
```

5. Inspect `data/out_data/<granule>_composited.nc`.

Expected checks:

- original root/group hierarchy is preserved;
- `/Land_Parameter_Average/DHR` still exists at the same path;
- DHR now uses `(Latitude, Longitude, rgb_band)` with `rgb_band=3`;
- RGB order is red, green, blue;
- the original MISR `Band=4` dimension remains available for unrelated variables;
- non-target variables and metadata are preserved;
- DHR values are display-scaled to `[0, 255]`;
- configured nodata remains output fill/nodata;
- CRS/grid-mapping metadata remains available.

This output is intended for Net2Cog, which supports one non-spatial band
dimension, followed by HyBIG, which handles a three-band raster as RGB.
