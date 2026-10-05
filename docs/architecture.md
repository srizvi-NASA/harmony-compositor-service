# Architecture

The Compositor is split into four responsibilities so that Harmony integration,
configuration discovery, validation, and science processing can evolve
independently.

## Harmony adapter

`adapter.py` handles Harmony-specific concerns only: selecting the STAC data
asset, downloading it with `harmony-service-lib`, retrieving the external
configuration, invoking the core processor, staging the output, and returning a
new STAC data asset.

## Configuration discovery

`config_utility.py` searches the Harmony source's UMM-Var RelatedURLs for:

```text
DistributionURL > SERVICE CONFIGURATION > COMPOSITOR CONFIGURATION
```

The URL is the source of truth.  There is intentionally no hard-coded
collection-to-configuration map in Python.

## Validation

`config_validator.py` performs JSON-schema validation and a small semantic pass
for relationships that draft-07 JSON Schema cannot express conveniently, such
as ensuring channel order matches the declared channels and clip minimum does
not exceed maximum.

## Composition core

`core.py` is Harmony-independent.  It:

1. opens the configured netCDF group/variable;
2. validates the configured Band dimension and coordinate;
3. resolves channel bands from coordinate labels;
4. converts configured source nodata values to NaN;
5. clips channel values;
6. stacks channels in configured output order;
7. preserves useful source attributes and grid-mapping support variables; and
8. writes the multi-channel netCDF output.

The core never contains MISR numeric band indices.  The MISR-specific path and
labels live in the external configuration.
