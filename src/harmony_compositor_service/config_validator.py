"""JSON-schema validation helpers for Compositor configuration files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema

from harmony_compositor_service.exceptions import ConfigurationError


def _load_schema(schema_file: str | Path) -> dict[str, Any]:
    """Load a JSON schema from disk and report a service-specific error."""
    try:
        with open(schema_file, "r", encoding="utf-8") as stream:
            schema = json.load(stream)
    except Exception as exc:
        raise ConfigurationError(f"Error loading schema: {exc}") from exc

    if not isinstance(schema, dict):
        raise ConfigurationError("Configuration schema must contain a JSON object.")
    return schema


def _validate_semantics(config: dict[str, Any]) -> None:
    """Validate relationships that are awkward to express in draft-07 JSON Schema."""
    clip = config["processing"]["clip"]
    if float(clip["min"]) > float(clip["max"]):
        raise ConfigurationError(
            "Configuration validation error at 'processing/clip': min must be <= max."
        )

    channel_names = [channel["name"] for channel in config["channels"]]
    if len(channel_names) != len(set(channel_names)):
        raise ConfigurationError(
            "Configuration validation error at 'channels': channel names must be unique."
        )

    channel_order = config["output"]["channel_order"]
    if set(channel_order) != set(channel_names):
        raise ConfigurationError(
            "Configuration validation error at 'output/channel_order': values must "
            "match the configured channel names exactly."
        )


def validate_config(config: dict[str, Any], schema_file: str | Path) -> dict[str, Any]:
    """Validate an in-memory compositor configuration against schema and semantics."""
    schema = _load_schema(schema_file)
    try:
        jsonschema.validate(instance=config, schema=schema)
    except jsonschema.ValidationError as exc:
        location = "/".join(str(part) for part in exc.absolute_path)
        suffix = f" at '{location}'" if location else ""
        raise ConfigurationError(
            f"Configuration validation error{suffix}: {exc.message}"
        ) from exc
    except jsonschema.SchemaError as exc:
        raise ConfigurationError(f"Invalid configuration schema: {exc.message}") from exc

    _validate_semantics(config)
    return config


def load_and_validate_config(
    config_file: str | Path, schema_file: str | Path
) -> dict[str, Any]:
    """Load a local configuration JSON file and validate it against a schema."""
    try:
        with open(config_file, "r", encoding="utf-8") as stream:
            config = json.load(stream)
    except Exception as exc:
        raise ConfigurationError(f"Error loading configuration: {exc}") from exc

    if not isinstance(config, dict):
        raise ConfigurationError("Configuration must contain a JSON object.")
    return validate_config(config, schema_file)
