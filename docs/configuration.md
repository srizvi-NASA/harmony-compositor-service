# Compositor configuration

The first schema is intentionally small.  Fields should be added only when a
new supported recipe requires a reusable capability.

## Metadata

`metadata` identifies the recipe and schema.  `config_type` must be
`compositor`.

## Input

`input.variable` may be a grouped netCDF path such as:

```text
/Land_Parameter_Average/DHR
```

`band_dimension` names the dimension containing bands. `band_coordinate`
identifies the coordinate whose values are used for selection. If omitted, the
band dimension itself is used as the coordinate name.

## Channels

Each channel gives a logical output name and a coordinate value to select. For
MISR natural color, the values are wavelength-labelled Band coordinate values,
not fixed indices.

## Processing

The initial reusable processing operations are source nodata translation and
numeric clipping.  Nodata is converted to NaN before clipping so a fill value
cannot accidentally become valid display data.

## Output

The output section specifies the multi-channel variable name, channel
dimension, explicit channel order, output floating-point type, and fill value.
