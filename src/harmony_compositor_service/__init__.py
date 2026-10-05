"""Harmony Compositor Service.

The package implements a configuration-driven multi-band compositor for
Harmony.  The initial supported recipe is MISR DHR natural color, while the
configuration and processing layers are intentionally generic enough for
additional products to be introduced later.
"""

try:
    from importlib.metadata import version

    __version__ = version("harmony-compositor")
except Exception:  # pragma: no cover - package metadata is absent in source trees
    __version__ = "0.0.0"
