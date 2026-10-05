"""Discover and retrieve externally hosted Compositor configuration.

Compositor configuration is curated in UMM-Var as a RelatedURL using the
controlled-vocabulary path::

    DistributionURL > SERVICE CONFIGURATION > COMPOSITOR CONFIGURATION

This mirrors the current Filtering Service pattern while intentionally using a
separate subtype so each Harmony service can discover only its own metadata.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import requests

from harmony_compositor_service.config_validator import validate_config
from harmony_compositor_service.exceptions import ConfigurationError

COMPOSITOR_URL_CONTENT_TYPE = "DistributionURL"
COMPOSITOR_URL_TYPE = "SERVICE CONFIGURATION"
COMPOSITOR_URL_SUBTYPE = "COMPOSITOR CONFIGURATION"
DEFAULT_REQUEST_TIMEOUT_SECONDS = 10


def _field(obj: Any, name: str, default: Any = None) -> Any:
    """Read a field from a Harmony message model or an ordinary dictionary."""
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _norm(value: Any) -> str:
    """Normalize UMM controlled-vocabulary text for robust comparison."""
    return str(value or "").strip().upper()


def _is_compositor_config_related_url(related_url: Any) -> bool:
    """Return ``True`` when a RelatedURL describes Compositor configuration."""
    return (
        _norm(_field(related_url, "urlContentType"))
        == COMPOSITOR_URL_CONTENT_TYPE.upper()
        and _norm(_field(related_url, "type")) == COMPOSITOR_URL_TYPE.upper()
        and _norm(_field(related_url, "subtype"))
        == COMPOSITOR_URL_SUBTYPE.upper()
    )


def _variable_name(variable: Any) -> str:
    """Return a Harmony source variable name when one is present."""
    return str(_field(variable, "name", "") or "")


def get_compositor_config_url(
    source: Any, requested_variable: str | None = None
) -> str:
    """Find a Compositor configuration URL in the Harmony source variables.

    When ``requested_variable`` is supplied, its UMM-Var record is searched
    first.  This matches the external-configuration pattern already used by the
    Filtering Service and avoids embedding collection-to-config mappings in the
    service code.
    """
    variables = _field(source, "variables", None)
    if not variables:
        raise ConfigurationError(
            "No variables were provided in the Harmony source; cannot locate "
            "a Compositor configuration RelatedURL."
        )

    variables = list(variables)
    if requested_variable:
        matching = [v for v in variables if _variable_name(v) == requested_variable]
        if matching:
            variables = matching + [v for v in variables if v not in matching]

    for variable in variables:
        for related_url in _field(variable, "relatedUrls", []) or []:
            if _is_compositor_config_related_url(related_url):
                url = _field(related_url, "url", "")
                if url:
                    return str(url)

    raise ConfigurationError(
        "No UMM-Var RelatedURL was found for DistributionURL > "
        "SERVICE CONFIGURATION > COMPOSITOR CONFIGURATION."
    )


def get_remote_compositor_config(
    url: str,
    schema_file: str | Path,
    timeout: int = DEFAULT_REQUEST_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Download, parse, and schema-validate externally hosted configuration."""
    try:
        response = requests.get(url, timeout=timeout)
    except requests.RequestException as exc:
        raise ConfigurationError(
            f"Failed to retrieve Compositor configuration at {url}: {exc}"
        ) from exc

    if not response.ok:
        raise ConfigurationError(
            f"Failed to retrieve Compositor configuration at {url}: "
            f"HTTP {response.status_code}"
        )

    try:
        config = response.json()
    except ValueError as exc:
        raise ConfigurationError(
            f"Compositor configuration at {url} is not valid JSON: {exc}"
        ) from exc

    if not isinstance(config, dict):
        raise ConfigurationError(
            f"Compositor configuration at {url} must contain a JSON object."
        )

    return validate_config(config, schema_file)


def get_compositor_config_from_source(
    source: Any,
    schema_file: str | Path,
    requested_variable: str | None = None,
) -> tuple[dict[str, Any], str]:
    """Discover and retrieve the Compositor configuration for a Harmony source."""
    url = get_compositor_config_url(source, requested_variable=requested_variable)
    return get_remote_compositor_config(url, schema_file), url
