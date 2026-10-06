# Architecture

The Compositor separates Harmony integration, configuration discovery,
validation, and science processing.

## Harmony adapter

`adapter.py` selects/downloads the STAC data asset, retrieves the external
configuration, invokes the core processor, stages the output, and returns the
new STAC data asset.

## Configuration discovery

`config_utility.py` searches UMM-Var RelatedURLs for:

```text
DistributionURL > SERVICE CONFIGURATION > COMPOSITOR CONFIGURATION
```

There is no hard-coded collection-to-configuration mapping in Python.

## Validation

`config_validator.py` validates the JSON schema plus relationships such as:
channel order matching channel definitions, valid clip/display ranges, output
variable matching input variable for structure-preserving replacement, and use
of a new RGB channel dimension rather than repurposing the source band dimension.

## Composition core

`core.py`:

1. opens the configured grouped source variable;
2. resolves channels by coordinate labels;
3. converts configured nodata to NaN and clips source data;
4. scales clipped values to the configured display range;
5. stacks exactly three channels in configured RGB order;
6. recursively copies the original NetCDF hierarchy using netCDF4;
7. replaces only the configured target variable at the same group/name with the
   three-channel composite; and
8. preserves unrelated dimensions, variables, groups, and attributes.

For MISR, the original `Band=4` dimension is retained because other variables
may depend on it. DHR alone is recreated with a dedicated `rgb_band=3`
dimension. This output is designed to pass directly through Net2Cog to HyBIG.
