"""
Config classes, the registry, and the module-level API.

A config class is an `attrs` class decorated with `@config`. Decoration registers the class as a settings group;
`get_config` creates its one instance on first use and fills it from `QSettings`. Every attribute assignment on
that instance is coerced to the declared type, run through the field's converter and validators, stored on the
instance, written to `QSettings`, and then announced on `signals().sig_value_changed`.
"""

from __future__ import annotations

import dataclasses
import logging
import typing
import warnings
from collections.abc import Callable, Iterable, Iterator, Mapping
from typing import Any, NamedTuple, dataclass_transform, overload
from warnings import deprecated

import attrs
from PySide6 import QtCore, QtGui, QtWidgets

from pyside_config._hooks import EditorHooks
from pyside_config._settings import coerce, settings, to_storable

_log = logging.getLogger("pyside_config")

_METADATA_KEY = "pyside_config"


class _FieldMeta(NamedTuple):
    """What `config_field` records about a field, stored under `_METADATA_KEY` in the attrs metadata."""

    label: str | None = None
    description: str = ""
    editor: Callable[[], QtWidgets.QWidget] | None = None
    icon: QtGui.QIcon | None = None
    hooks: EditorHooks | None = None
    qtype: Any = None


_NO_META = _FieldMeta()


def config_field(
    default: Any = attrs.NOTHING,
    *,
    factory: Callable[[], Any] | None = None,
    label: str | None = None,
    description: str = "",
    editor: Callable[[], QtWidgets.QWidget] | None = None,
    icon: QtGui.QIcon | None = None,
    hooks: EditorHooks | None = None,
    qtype: Any = None,
    metadata: Mapping[str, Any] | None = None,
    **kwargs: Any,
) -> Any:
    """
    Declares one setting. It is `attrs.field` plus what the settings dialog and `iter_fields` need.

    Args:
        default: The value used when nothing is stored. Every field needs `default` or `factory`.
        factory: Zero-argument callable producing the default. Use it for mutable defaults such as `list`.
        label: Title of the field in the dialog. Defaults to the field name with underscores as spaces.
        description: Text shown under the label; also available through `iter_fields`.
        editor: Zero-argument callable returning the widget that edits the field. A field without an editor
            is stored but not shown in the dialog. Set Qt properties in the constructor call.
        icon: Icon shown left of the label.
        hooks: How the dialog reads, writes and watches the editor. Only needed for a widget that has neither a
            Qt USER property nor hooks registered with `register_editor_hooks`.
        qtype: Type to coerce stored values to, when the annotation is not the right target.
        metadata: Extra `attrs` metadata of your own.
        **kwargs: Passed to `attrs.field` (`converter`, `validator`, ...).

    Raises:
        TypeError: `editor` is not callable.

    Example:
        ```python
        click_radius: int = config_field(
            default=20,
            label="Click radius",
            description="Pixels around a click searched for an extreme point.",
            editor=lambda: QtWidgets.QSpinBox(minimum=0, maximum=1000, suffix=" px"),
        )
        ```
    """
    if editor is not None and not callable(editor):
        raise TypeError(
            f"editor must be a zero-argument callable returning a QWidget, not {type(editor).__name__}. "
            "EditorWidgetInfo and the make_*_info helpers were removed in 0.3; see CHANGELOG.md."
        )
    merged: dict[str, Any] = dict(metadata or {})
    merged[_METADATA_KEY] = _FieldMeta(label, description, editor, icon, hooks, qtype)
    if factory is not None:
        return attrs.field(factory=factory, metadata=merged, **kwargs)
    return attrs.field(default=default, metadata=merged, **kwargs)


def field_meta(field: attrs.Attribute[Any]) -> _FieldMeta:
    return field.metadata.get(_METADATA_KEY, _NO_META)


def field_label(field: attrs.Attribute[Any]) -> str:
    """The label given to `config_field`, or the field name with underscores as spaces."""
    return field_meta(field).label or field.name.replace("_", " ").capitalize()


def editable_fields(config_class: type) -> list[attrs.Attribute[Any]]:
    """The fields of `config_class` that have an editor, in declaration order."""
    return [f for f in attrs.fields(config_class) if field_meta(f).editor is not None]


def _field_type(field: attrs.Attribute[Any]) -> Any:
    return field_meta(field).qtype or field.type


def _raw_default(field: attrs.Attribute[Any], inst: Any = None) -> Any:
    default = field.default
    if isinstance(default, attrs.Factory):  # type: ignore[arg-type]
        return default.factory(inst) if default.takes_self else default.factory()  # type: ignore[union-attr]
    return default


def default_value(inst: Any, field: attrs.Attribute[Any]) -> Any:
    """The value a new instance holds for `field`: the declared default after the field's converter."""
    return attrs.setters.convert(inst, field, _raw_default(field, inst))


def prepare_value(inst: Any, field: attrs.Attribute[Any], value: Any) -> Any:
    """
    Turns `value` into what assigning it to `field` would store, without storing it.

    Coerces to the declared type (skipped when the field has a converter), then runs the converter and the
    validators. Raises whatever those raise, normally `ValueError` or `TypeError`.
    """
    if field.converter is None:
        value = coerce(value, _field_type(field))
    value = attrs.setters.convert(inst, field, value)
    return attrs.setters.validate(inst, field, value)


def values_equal(a: Any, b: Any) -> bool:
    try:
        return bool(a == b)
    except Exception:  # array-likes whose comparison has no single truth value
        return False


class GroupInfo(NamedTuple):
    """One registered settings group, as returned by `group_info` and `groups`."""

    name: str
    """The `QSettings` group the fields are stored under."""
    title: str
    """The text shown for the group in the dialog."""
    hidden: bool
    """Whether the group is left out of the dialog."""
    config_class: type
    """The decorated class."""


@dataclasses.dataclass(eq=False)
class _Group:
    """Registry entry: the group's declaration and, once `get_config` was called, its instance."""

    name: str
    title: str
    hidden: bool
    config_class: type
    instance: Any = None

    def info(self) -> GroupInfo:
        return GroupInfo(self.name, self.title, self.hidden, self.config_class)

    def path(self, field: attrs.Attribute[Any]) -> str:
        return f"{self.name}/{field.name}"


_groups: dict[str, _Group] = {}
_groups_by_class: dict[type, _Group] = {}


class FieldInfo(NamedTuple):
    """One declared setting, as yielded by `iter_fields`."""

    group: str
    name: str
    type: Any
    default: Any
    label: str
    description: str
    hidden: bool
    has_editor: bool

    @property
    def editable(self) -> bool:
        """Whether the field has an editor and its group is shown in the dialog."""
        return self.has_editor and not self.hidden


class ConfigSignals(QtCore.QObject):
    """
    Signals of the package. Get the instance with `signals()`.

    `sig_value_changed(group, name, value)` fires after a field of a registered config instance changed to a
    different value. The instance already holds the new value when the signal arrives.
    """

    sig_value_changed = QtCore.Signal(str, str, object)


_signals: ConfigSignals | None = None


def signals() -> ConfigSignals:
    """The package's `ConfigSignals` object, created on first use."""
    global _signals
    if _signals is None:
        _signals = ConfigSignals()
    return _signals


@overload
@dataclass_transform(eq_default=False, field_specifiers=(config_field,))
def config[C: type](cls: C, /) -> C: ...
@overload
def config[C: type](
    *,
    group: str | None = None,
    title: str | None = None,
    hidden: bool = False,
    register: bool = True,
    group_name: str | None = None,
) -> Callable[[C], C]: ...
def config(
    cls: Any = None,
    /,
    *,
    group: str | None = None,
    title: str | None = None,
    hidden: bool = False,
    register: bool = True,
    group_name: str | None = None,
) -> Any:
    """
    Turns a class into a settings group.

    The class becomes an `attrs` class. Nothing is read from `QSettings` until the first `get_config` call.

    Args:
        group: The `QSettings` group the fields are stored under. Defaults to the class name. Changing it
            orphans the values users have stored.
        title: The text shown for the group in the dialog. Defaults to `group`. Safe to change at any time.
        hidden: Leave the group out of the dialog.
        register: Set to `False` for a base class that only contributes fields to subclasses.
        group_name: Deprecated name of `group`.

    Raises:
        TypeError: A field has no default, or an annotation cannot be resolved to a type.
        ValueError: A group of that name is already registered.

    Example:
        ```python
        @config(group="Plot")
        class PlotConfig:
            click_radius: int = config_field(default=20)

        plot = get_config(PlotConfig)
        plot.click_radius = 30  # written to QSettings, sig_value_changed emitted
        ```
    """
    if group_name is not None:
        warnings.warn("config(group_name=...) is deprecated, use group=. Removed in 0.4.", DeprecationWarning, 2)
        group = group or group_name

    def wrap(target: Any) -> Any:
        config_class = attrs.define(target, eq=False, on_setattr=prepare_value)
        _resolve_types(config_class)
        for field in attrs.fields(config_class):
            if field.default is attrs.NOTHING:
                raise TypeError(f"{config_class.__name__}.{field.name} needs a default or a factory.")
        if register:
            name = group or config_class.__name__
            if name in _groups:
                raise ValueError(f"A config group named '{name}' is already registered.")
            record = _Group(name, title or name, hidden, config_class)
            _write_through(config_class, record)
            _groups[name] = record
            _groups_by_class[config_class] = record
        return config_class

    return wrap if cls is None else wrap(cls)


def _resolve_types(config_class: type) -> None:
    """Replaces string annotations by the types they name. Coercion needs real types."""
    try:
        attrs.resolve_types(config_class)
    except Exception as exc:
        unresolved = [f.name for f in attrs.fields(config_class) if isinstance(f.type, (str, typing.ForwardRef))]
        if unresolved:
            raise TypeError(
                f"Cannot resolve the annotation of {config_class.__name__}.{unresolved[0]}: {exc}. "
                "Import the type at runtime (not under TYPE_CHECKING) or pass qtype= to config_field."
            ) from exc


def _write_through(config_class: Any, record: _Group) -> None:
    """Makes assignments on the registered instance write to `QSettings` and emit, after attrs stored the value."""
    attrs_setattr = config_class.__setattr__
    fields = {f.name: f for f in attrs.fields(config_class)}

    def __setattr__(self: Any, name: str, value: Any) -> None:
        field = fields.get(name)
        if field is None or self is not record.instance:
            attrs_setattr(self, name, value)
            return
        old = getattr(self, name)
        attrs_setattr(self, name, value)  # coerce, convert, validate, store
        new = getattr(self, name)
        settings().setValue(record.path(field), to_storable(new))
        if not values_equal(old, new):
            signals().sig_value_changed.emit(record.name, name, new)

    config_class.__setattr__ = __setattr__


def _record(group: type | str) -> _Group:
    try:
        return _groups[group] if isinstance(group, str) else _groups_by_class[group]
    except KeyError:
        if isinstance(group, str):
            raise KeyError(f"No config group named '{group}' is registered.") from None
        raise KeyError(f"{group.__name__} is not a registered config class.") from None


def _stored_or_default(record: _Group, inst: Any, field: attrs.Attribute[Any]) -> Any:
    """The stored value of `field` in the field's type, or the default when nothing usable is stored."""
    store = settings()
    path = record.path(field)
    if not store.contains(path):
        return default_value(inst, field)
    raw = store.value(path)
    try:
        return prepare_value(inst, field, raw)
    except Exception as exc:
        _log.warning("Ignoring the stored value %r of %s, using the default: %s", raw, path, exc)
        return default_value(inst, field)


def _load(record: _Group) -> Any:
    inst = record.config_class()
    for field in attrs.fields(record.config_class):
        object.__setattr__(inst, field.name, _stored_or_default(record, inst, field))
    return inst


def _refresh(record: _Group) -> None:
    """Re-reads the store into an existing instance and emits `sig_value_changed` for each field that changed."""
    inst = record.instance
    for field in attrs.fields(record.config_class):
        old = getattr(inst, field.name)
        new = _stored_or_default(record, inst, field)
        object.__setattr__(inst, field.name, new)
        if not values_equal(old, new):
            signals().sig_value_changed.emit(record.name, field.name, new)


@overload
def get_config[C](group: type[C]) -> C: ...
@overload
def get_config(group: str) -> Any: ...
def get_config(group: Any) -> Any:
    """
    Returns the instance of a registered config class, by class or by group name.

    The first call for a group creates the instance and reads its values from `QSettings`. A stored value that
    cannot be coerced or that a converter or validator rejects is logged as a warning on the `pyside_config`
    logger and replaced by the default.

    Raises:
        KeyError: Nothing is registered under that class or name.
    """
    record = _record(group)
    if record.instance is None:
        record.instance = _load(record)
    return record.instance


def group_info(group: type | str) -> GroupInfo:
    """
    The name, title, hidden flag and class of a registered group, by class or by group name.

    Raises:
        KeyError: Nothing is registered under that class or name.
    """
    return _record(group).info()


def groups() -> list[GroupInfo]:
    """Every registered group, in registration order."""
    return [record.info() for record in _groups.values()]


def unregister(group: type | str) -> None:
    """
    Removes a group from the registry. Stored values are kept.

    Raises:
        KeyError: Nothing is registered under that class or name.
    """
    record = _record(group)
    del _groups[record.name]
    del _groups_by_class[record.config_class]


def clear_registry() -> None:
    """Removes every group from the registry. For tests that declare groups; stored values are kept."""
    _groups.clear()
    _groups_by_class.clear()


def sync() -> None:
    """
    Flushes pending writes to permanent storage.

    Every assignment already reaches the `QSettings` object. `sync` forces the write to disk or registry, which
    Qt otherwise does at intervals and when the `QSettings` object is destroyed.
    """
    settings().sync()


def reload() -> None:
    """
    Re-reads the store into every existing instance.

    Use it after `configure` replaced the store or after another process changed it. Emits `sig_value_changed`
    for each field whose value changed.
    """
    settings().sync()
    for record in _groups.values():
        if record.instance is not None:
            _refresh(record)


def restore_defaults(*groups: type | str) -> None:
    """
    Removes the stored values of the given groups, or of every registered group when none is given.

    The instances go back to their declared defaults and `sig_value_changed` fires for each field that changed.
    Because the keys are removed, a default changed in a later release reaches the user.

    Raises:
        KeyError: A group is not registered.
    """
    records = [_record(g) for g in groups] if groups else list(_groups.values())
    store = settings()
    for record in records:
        for field in attrs.fields(record.config_class):
            store.remove(record.path(field))
    store.sync()
    for record in records:
        if record.instance is not None:
            _refresh(record)


def clear_store() -> None:
    """
    Deletes everything in the store, including keys this package never wrote, then reloads the instances.

    Unlike `restore_defaults` it needs no registered group, so it works before the config classes are imported.
    """
    settings().clear()
    reload()


def iter_fields(include_hidden: bool = True) -> Iterator[FieldInfo]:
    """
    Yields one `FieldInfo` per declared setting, in declaration order.

    Use it to generate documentation or to check documentation against the declarations. No instance is created
    and nothing is read from `QSettings`.
    """
    for record in _groups.values():
        if record.hidden and not include_hidden:
            continue
        for field in attrs.fields(record.config_class):
            meta = field_meta(field)
            yield FieldInfo(
                group=record.name,
                name=field.name,
                type=_field_type(field),
                default=_raw_default(field),
                label=field_label(field),
                description=meta.description,
                hidden=record.hidden,
                has_editor=meta.editor is not None,
            )


@deprecated("save() is replaced by sync(). Removed in 0.4.")
def save() -> None:
    """Deprecated alias of `sync`. It no longer writes default values to the store."""
    sync()


@deprecated("reset() is replaced by restore_defaults(). Removed in 0.4.")
def reset(exclude: Iterable[str] | None = None) -> None:
    """Deprecated. Restores the defaults of every registered group except those named in `exclude`."""
    skip = set(exclude or ())
    names = [name for name in _groups if name not in skip]
    if names:
        restore_defaults(*names)


@deprecated("clean() is replaced by clear_store(). Removed in 0.4.")
def clean(exclude: Iterable[str] | None = None) -> None:
    """Deprecated. Deletes every top-level group of the store not named in `exclude`, then reloads."""
    if not exclude:
        clear_store()
        return
    store = settings()
    skip = set(exclude)
    for name in list(store.childGroups()):
        if name not in skip:
            store.remove(name)
    reload()
