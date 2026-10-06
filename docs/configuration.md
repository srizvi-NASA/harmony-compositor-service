# Compositor configuration

The first production recipe is MISR DHR natural color. Product-specific band
labels remain in external JSON rather than Python source.

## Metadata

`metadata` identifies the recipe and schema. `config_type` must be `compositor`.

## Input

`input.variable` is the grouped netCDF path to the source variable, for example:

```text
/Land_Parameter_Average/DHR
```

`band_dimension` identifies the source band dimension. `band_coordinate`
identifies the coordinate whose labels are used to select channels. MISR bands
are selected by labels such as `red_672nm`, not by hard-coded indices.

## Channels

Each entry maps a logical output channel (`red`, `green`, or `blue`) to a
source coordinate value.

## Processing

Configured nodata values are translated to NaN before clipping. The MISR recipe
clips DHR to `[0, 1]`.

## Output

Compositor preserves the input NetCDF hierarchy. `output.variable` must match
`input.variable`, so the target variable is replaced at the same group/name.
All unrelated groups, dimensions, variables, and attributes are copied forward.

The target variable receives a new three-element channel dimension rather than
reusing or shrinking the source `Band` dimension. This is important because
other variables in the granule may still use the original four-element MISR
`Band` dimension.

`display_range` linearly maps the clipped science range into display-ready RGB
values. For MISR DHR, `[0, 1]` maps to `[0, 255]`. The sample recipe keeps the
output as `float32` with `-9999` fill so nodata remains distinct from valid black
or white pixels.

The expected replacement variable is therefore:

```text
/Land_Parameter_Average/DHR(Latitude, Longitude, rgb_band=3)
```

with channel order red, green, blue.
