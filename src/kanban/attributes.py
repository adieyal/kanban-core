"""JSON card attributes and their detached, immutable read representation."""

from __future__ import annotations

import math
from collections.abc import Mapping
from types import MappingProxyType

from .exceptions import ValidationError


def copy_attributes(attributes: object) -> dict[str, object]:
    """Validate and copy a JSON object without retaining caller-owned containers."""
    if not isinstance(attributes, Mapping):
        raise ValidationError("Card attributes must be a JSON object")
    if any(not isinstance(key, str) for key in attributes):
        raise ValidationError("Card attribute object keys must be strings")
    active: set[int] = set()

    def copy_value(value: object) -> object:
        if value is None or isinstance(value, str | bool | int):
            return value
        if isinstance(value, float):
            if not math.isfinite(value):
                raise ValidationError("Card attributes require finite JSON numbers")
            return value
        if not isinstance(value, Mapping | list | tuple):
            raise ValidationError("Card attributes must contain only JSON values")
        if id(value) in active:
            raise ValidationError("Card attributes must not contain cycles")
        active.add(id(value))
        try:
            if isinstance(value, list | tuple):
                return [copy_value(item) for item in value]
            if any(not isinstance(key, str) for key in value):
                raise ValidationError("Card attribute object keys must be strings")
            return {key: copy_value(item) for key, item in value.items()}
        finally:
            active.remove(id(value))

    try:
        return {key: copy_value(value) for key, value in attributes.items()}
    except RecursionError as error:
        raise ValidationError("Card attributes are nested too deeply") from error


def freeze_attributes(attributes: Mapping[str, object]) -> Mapping[str, object]:
    """Copy dictionaries to read-only mappings and JSON arrays to tuples."""

    def freeze_value(value: object) -> object:
        if isinstance(value, Mapping):
            return MappingProxyType(
                {key: freeze_value(item) for key, item in value.items()}
            )
        if isinstance(value, list | tuple):
            return tuple(freeze_value(item) for item in value)
        return value

    return MappingProxyType(
        {key: freeze_value(value) for key, value in attributes.items()}
    )
