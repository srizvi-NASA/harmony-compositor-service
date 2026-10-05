# Local validation performed during repository generation

The generated source was syntax-compiled and the locally runnable unit suite was
executed successfully in the artifact environment.

```text
13 passed, 1 skipped
```

The skipped test is the grouped netCDF4 MISR-style integration/unit test because
`netCDF4` is not installed in the artifact-generation environment. It is part of
the repository and will run in the normal project/CI environment, where
`netCDF4` is a declared dependency.

`uv lock --check` also completed successfully against the included lock file.

Docker image execution was not performed in the artifact-generation environment
because Docker is not available there. Docker files were derived from the
provided working Filtering Service baseline and adapted for Compositor.
