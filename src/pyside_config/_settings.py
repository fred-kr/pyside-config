"""
`QSettings` access and value coercion.

The package reads and writes through one `QSettings` object created on first use (`settings`). By default that is
`QSettings()`, which needs `QCoreApplication.setOrganizationName` and `setApplicationName` to have been called.
Tests and embedding applications replace it with `configure`.

`coerce` repairs the types `QSettings` returns: INI backends hand back every scalar as `str`, the Windows registry
returns `bool` as `"true"`/`"false"`, and a one-element string list comes back as a plain `str`.
"""

from __future__ import annotations

import collections.abc
import decimal
import enum
import math
import pathlib
import types
import typing
from collections.abc import Callable
from typing import Any

from PySide6 import QtCore

_factory: Callable[[], QtCore.QSettings] | None = None
_instance: QtCore.QSettings | None = None


def configure(settings_factory: Callable[[], QtCore.QSettings] | None = None) -> None:
    """
    Sets how the package creates its `QSettings`.

    Call it before the first `@config` class is declared. Passing `None` restores the default, `QSettings()`.
    The cached `QSettings` object is dropped either way, so a later call creates a new one.

    Example:
        ```python
        pyside_config.configure(lambda: QtCore.QSettings("settings.ini", QtCore.QSettings.Format.IniFormat))
        ```
    """
    global _factory, _instance
    _factory = settings_factory
    _instance = None


def settings() -> QtCore.QSettings:
    """
    The `QSettings` object the package stores values in.

    Raises:
        RuntimeError: No factory was configured and the organization or application name is not set.
    """
    global _instance
    if _instance is None:
        if _factory is not None:
            _instance = _factory()
        else:
            if not QtCore.QCoreApplication.organizationName() or not QtCore.QCoreApplication.applicationName():
                raise RuntimeError(
                    "pyside_config needs QCoreApplication.setOrganizationName() and setApplicationName() to be "
                    "called before the first @config class is declared, or a QSettings factory passed to "
                    "pyside_config.configure()."
                )
            _instance = QtCore.QSettings()
    return _instance


_TRUE = frozenset({"true", "1", "yes", "on"})
_FALSE = frozenset({"false", "0", "no", "off", ""})


def to_storable(value: Any) -> Any:
    """Converts a Python value to something every `QSettings` backend can persist and `coerce` can read back."""
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, (decimal.Decimal, pathlib.PurePath)):
        return str(value)
    if isinstance(value, (list, tuple, set, frozenset)):
        return [to_storable(v) for v in value]
    if isinstance(value, dict):
        return {k: to_storable(v) for k, v in value.items()}
    return value


def coerce(value: Any, type_: Any) -> Any:
    """
    Converts `value`, as returned by `QSettings.value`, to `type_`.

    Supports `bool`, `int`, `float`, `str`, `bytes`, `decimal.Decimal`, `pathlib.Path`, `QByteArray`, `Enum`
    subclasses (matched by value, then by name), `X | None`, `Literal`, `list[T]`, `tuple[T, ...]`,
    `tuple[A, B]` (one type per position), `set[T]`, `dict[K, V]` and any class that accepts the value as its
    single constructor argument. `None` and `Any` as `type_` return `value` unchanged.

    A number with a fractional part is not an `int`: `coerce("5.0", int)` is `5`, `coerce(2.7, int)` raises.

    Raises:
        ValueError, TypeError: `value` cannot be interpreted as `type_`.
    """
    if type_ is None or type_ is Any or isinstance(type_, (str, typing.ForwardRef, typing.TypeVar)):
        return value

    origin = typing.get_origin(type_)
    args = typing.get_args(type_)

    if origin is typing.Union or origin is types.UnionType:
        members = [a for a in args if a is not type(None)]
        if value is None and len(members) < len(args):
            return None
        last_error: Exception | None = None
        for member in members:
            try:
                return coerce(value, member)
            except (ValueError, TypeError) as exc:
                last_error = exc
        raise ValueError(f"{value!r} does not match any of {type_}") from last_error

    if origin is typing.Literal:
        if value in args:
            return value
        for option in args:
            try:
                if coerce(value, type(option)) == option:
                    return option
            except ValueError, TypeError:
                continue
        raise ValueError(f"{value!r} is not one of {args}")

    if origin in (list, tuple, set, frozenset, collections.abc.Sequence, collections.abc.MutableSequence):
        items = _to_list(value)
        if origin is tuple and args and Ellipsis not in args:
            if len(items) != len(args):
                raise ValueError(f"{value!r} does not have {len(args)} items")
            return tuple(coerce(v, t) for v, t in zip(items, args, strict=True))
        item_type = args[0] if args else None
        items = [coerce(v, item_type) for v in items]
        if origin is tuple:
            return tuple(items)
        if origin is set:
            return set(items)
        if origin is frozenset:
            return frozenset(items)
        return items

    if origin in (dict, collections.abc.Mapping, collections.abc.MutableMapping):
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise TypeError(f"{value!r} is not a mapping")
        key_type = args[0] if args else None
        value_type = args[1] if len(args) > 1 else None
        return {coerce(k, key_type): coerce(v, value_type) for k, v in value.items()}

    if origin is not None:
        type_ = origin

    if not isinstance(type_, type):
        return value

    if isinstance(value, type_) and not (type_ is int and isinstance(value, bool)):
        return value

    if type_ is bool:
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in _TRUE:
                return True
            if lowered in _FALSE:
                return False
            raise ValueError(f"{value!r} is not a boolean")
        if isinstance(value, (int, float)):
            return bool(value)
        if value is None:
            return False
        raise TypeError(f"{value!r} is not a boolean")

    if type_ is int:
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, str):
            text = value.strip()
            try:
                return int(text)
            except ValueError:
                value = float(text)
        if isinstance(value, (float, decimal.Decimal)):
            if not math.isfinite(value) or value != int(value):
                raise ValueError(f"{value!r} is not a whole number")
        return int(value)

    if type_ is float:
        return float(value)

    if type_ is str:
        if value is None:
            return ""
        if isinstance(value, QtCore.QByteArray):
            return bytes(value.data()).decode()
        if isinstance(value, bytes):
            return value.decode()
        return str(value)

    if type_ is bytes:
        if isinstance(value, QtCore.QByteArray):
            return bytes(value.data())
        if isinstance(value, str):
            return value.encode()
        return bytes(value)

    if type_ is list:
        return _to_list(value)

    if issubclass(type_, enum.Enum):
        if value is None:
            raise ValueError(f"None is not a member of {type_.__name__}")
        try:
            return type_(value)
        except ValueError:
            pass
        if isinstance(value, str):
            try:
                return type_[value]
            except KeyError:
                pass
            if issubclass(type_, int):
                return type_(int(value))
        raise ValueError(f"{value!r} is not a member of {type_.__name__}")

    if type_ is QtCore.QByteArray:
        if value is None:
            return QtCore.QByteArray()
        if isinstance(value, (bytes, bytearray)):
            return QtCore.QByteArray(bytes(value))
        if isinstance(value, str):
            return QtCore.QByteArray(value.encode())
        raise TypeError(f"{value!r} is not a QByteArray")

    if type_ is decimal.Decimal:
        return decimal.Decimal(str(value))

    if issubclass(type_, pathlib.PurePath):
        return type_(str(value))

    return type_(value)


def _to_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, (list, tuple, set, frozenset)):
        return list(value)
    raise TypeError(f"{value!r} is not a list")
