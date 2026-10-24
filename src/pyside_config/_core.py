"""
Config classes, the registry, and the module-level API.

A config class is an `attrs` class decorated with `@config`. Decoration registers one instance, filled from
`QSettings`; every attribute assignment on that instance is coerced to the declared type, run through the field's
converter and validators, written to `QSettings`, and announced on `signals().sig_value_changed`.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Mapping
from typing import TYPE_CHECKING, Any, ClassVar, NamedTuple, Protocol, Self, overload

import attrs
from PySide6 import QtCore, QtGui, QtWidgets

from pyside_config._hooks import EditorHooks, hooks_for
from pyside_config._settings import coerce, settings, to_storable

if TYPE_CHECKING:
    from pyside_config.properties import WidgetPropertiesBase

EDITOR_KEY = "editor"
"""Field metadata key holding the `EditorWidgetInfo`. Fields without it do not appear in the dialog."""

DESCRIPTION_KEY = "description"
"""Field metadata key holding the text shown under the editor."""

QTYPE_KEY = "__qtype"
"""Field metadata key overriding the type values are coerced to. Defaults to the field's annotation."""


class ConfigInstance(attrs.AttrsInstance, Protocol):
    """What `@config` adds to a class."""

    __group_prefix__: ClassVar[str]
    __hidden__: ClassVar[bool]

    @classmethod
    def from_qsettings(cls) -> Self: ...

    def to_qsettings(self) -> None: ...

    def restore_defaults(self) -> None: ...

    def create_editor(self, **kwargs: Any) -> QtWidgets.QScrollArea: ...


class EditorWidgetInfo[W: QtWidgets.QWidget | QtGui.QAction](NamedTuple):
    """
    How a field is edited in the settings dialog.

    `widget_factory` is called with the keyword arguments of `create_editor` (normally none). The signal and
    method names are optional: when omitted they come from the hooks registered for the widget's class
    (`pyside_config.hooks_for`), which cover the Qt input widgets and the pyside-widgets editors.
    """

    label: str
    widget_factory: Callable[..., W]
    sig_value_changed: str | None = None
    set_value_method: str | None = None
    get_value_method: str | None = None
    icon: QtGui.QIcon | None = None
    widget_properties: WidgetPropertiesBase[W] | None = None

    def hooks(self, widget: W) -> EditorHooks:
        """The hooks for `widget`: registered defaults, overridden by any names given here."""
        if self.sig_value_changed and self.set_value_method and self.get_value_method:
            return EditorHooks.from_names(self.sig_value_changed, self.get_value_method, self.set_value_method)
        base = hooks_for(widget)
        return EditorHooks(
            base.value_changed if self.sig_value_changed is None else _signal_getter(self.sig_value_changed),
            base.get_value if self.get_value_method is None else _method_caller(self.get_value_method),
            base.set_value if self.set_value_method is None else _method_setter(self.set_value_method),
        )


def _signal_getter(name: str) -> Callable[[Any], QtCore.SignalInstance]:
    return lambda editor: getattr(editor, name)


def _method_caller(name: str) -> Callable[[Any], Any]:
    return lambda editor: getattr(editor, name)()


def _method_setter(name: str) -> Callable[[Any, Any], None]:
    return lambda editor, value: getattr(editor, name)(value)


def config_field(
    default: Any = attrs.NOTHING,
    *,
    factory: Callable[[], Any] | None = None,
    editor: EditorWidgetInfo[Any] | None = None,
    description: str = "",
    qtype: type | None = None,
    metadata: Mapping[str, Any] | None = None,
    **kwargs: Any,
) -> Any:
    """
    `attrs.field` with the pyside-config metadata as keyword arguments.

    Args:
        default: The value used when nothing is stored. Mutually exclusive with `factory`.
        factory: Zero-argument callable producing the default.
        editor: How the dialog edits the field. Omit it for fields that are stored but not shown.
        description: Text shown under the editor.
        qtype: Type to coerce stored values to, when the annotation is not the right target.
        metadata: Extra metadata merged in.
        **kwargs: Passed to `attrs.field` (`converter`, `validator`, ...).

    Example:
        ```python
        click_radius: int = config_field(
            default=20,
            editor=make_spin_box_info("Click radius", minimum=0, maximum=1000, suffix=" px"),
            description="Pixels around a click searched for an extreme point.",
        )
        ```
    """
    merged: dict[str, Any] = dict(metadata or {})
    if editor is not None:
        merged[EDITOR_KEY] = editor
    if description:
        merged[DESCRIPTION_KEY] = description
    if qtype is not None:
        merged[QTYPE_KEY] = qtype
    if factory is not None:
        return attrs.field(factory=factory, metadata=merged, **kwargs)
    return attrs.field(default=default, metadata=merged, **kwargs)


class FieldInfo(NamedTuple):
    """One declared setting, as yielded by `iter_fields`."""

    group: str
    name: str
    type: Any
    default: Any
    label: str | None
    description: str
    hidden: bool

    @property
    def editable(self) -> bool:
        """Whether the field has an editor and its group is shown in the dialog."""
        return self.label is not None and not self.hidden


class ConfigSignals(QtCore.QObject):
    """
    Signals of the package. Get the instance with `signals()`.

    `sig_value_changed(group, name, value)` fires after an attribute of a registered config instance changed
    to a different value and was written to `QSettings`.
    """

    sig_value_changed = QtCore.Signal(str, str, object)


_signals: ConfigSignals | None = None


def signals() -> ConfigSignals:
    """The package's `ConfigSignals` object, created on first use."""
    global _signals
    if _signals is None:
        _signals = ConfigSignals()
    return _signals


_registry: dict[str, ConfigInstance] = {}
_class_names: dict[type, str] = {}


def _fields(cls: type) -> tuple[attrs.Attribute[Any], ...]:
    return attrs.fields(cls)


def _field_default(field: attrs.Attribute[Any]) -> Any:
    default = field.default
    if isinstance(default, attrs.Factory):  # type: ignore[arg-type]
        return default.factory()  # type: ignore[union-attr]
    return default


def _field_type(field: attrs.Attribute[Any]) -> Any:
    return field.metadata.get(QTYPE_KEY) or field.type


def _setting_path(cls_or_inst: ConfigInstance | type[ConfigInstance], field: attrs.Attribute[Any]) -> str:
    return f"{cls_or_inst.__group_prefix__}/{field.name}"


def _coerce_on_setattr(inst: ConfigInstance, field: attrs.Attribute[Any], value: Any) -> Any:
    if field.converter is not None:
        return value
    return coerce(value, _field_type(field))


def _write_on_setattr(inst: ConfigInstance, field: attrs.Attribute[Any], value: Any) -> Any:
    try:
        changed = getattr(inst, field.name) != value
    except Exception:
        changed = True
    settings().setValue(_setting_path(inst, field), to_storable(value))
    if changed:
        signals().sig_value_changed.emit(inst.__group_prefix__, field.name, value)
    return value


def _from_qsettings(cls: type[ConfigInstance]) -> ConfigInstance:
    store = settings()
    init_values: dict[str, Any] = {}
    for field in _fields(cls):
        path = _setting_path(cls, field)
        default = _field_default(field)
        if not store.contains(path):
            init_values[field.name] = default
            continue
        raw = store.value(path)
        if field.converter is not None:
            init_values[field.name] = raw
            continue
        try:
            init_values[field.name] = coerce(raw, _field_type(field))
        except ValueError, TypeError:
            init_values[field.name] = default
    return cls(**init_values)


def _to_qsettings(self: ConfigInstance) -> None:
    store = settings()
    for field in _fields(type(self)):
        store.setValue(_setting_path(self, field), to_storable(getattr(self, field.name)))


def _restore_defaults(self: ConfigInstance) -> None:
    for field in _fields(type(self)):
        setattr(self, field.name, _field_default(field))


def _create_editor(self: ConfigInstance, **kwargs: Any) -> QtWidgets.QScrollArea:
    from pyside_config._editor import build_group_page

    return build_group_page(self, staged=None, **kwargs)


@overload
def config[C: type](target_cls: C) -> C: ...
@overload
def config[C: type](
    *, group_name: str | None = None, register: bool = True, hidden: bool = False
) -> Callable[[C], C]: ...
def config[C: type](
    target_cls: C | None = None, *, group_name: str | None = None, register: bool = True, hidden: bool = False
) -> C | Callable[[C], C]:
    """
    Turns a class into a settings group.

    Args:
        group_name: The `QSettings` group the fields are stored under. Defaults to the class name.
        register: Create the instance and register it. Set to `False` for base classes.
        hidden: Keep the group out of `create_editor` and `iter_fields(include_hidden=False)`.

    Example:
        ```python
        @config(group_name="Plot")
        class PlotConfig:
            click_radius: int = config_field(default=20, description="...")

        plot = get_config(PlotConfig)
        plot.click_radius = 30  # written to QSettings, sig_value_changed emitted
        ```
    """

    def wrap(cls: C) -> C:
        cls.__group_prefix__ = group_name or cls.__name__
        cls.__hidden__ = hidden
        cls.from_qsettings = classmethod(_from_qsettings)
        cls.to_qsettings = _to_qsettings
        cls.restore_defaults = _restore_defaults
        cls.create_editor = _create_editor

        attrs_class = attrs.define(
            cls,
            eq=False,
            on_setattr=[_coerce_on_setattr, attrs.setters.convert, attrs.setters.validate, _write_on_setattr],
        )
        try:
            attrs.resolve_types(attrs_class)
        except Exception:
            pass
        if register:
            _register(attrs_class)
        return attrs_class

    return wrap if target_cls is None else wrap(target_cls)


def _register(config_class: type[ConfigInstance], overwrite: bool = False) -> None:
    name = config_class.__group_prefix__
    if name in _registry and not overwrite:
        raise ValueError(f"A config class named '{name}' is already registered.")
    _registry[name] = config_class.from_qsettings()
    _class_names[config_class] = name


def unregister(name: str) -> None:
    """Removes a registered group. Stored values are kept; use `clean` to delete them."""
    del _registry[name]
    for cls, registered in list(_class_names.items()):
        if registered == name:
            del _class_names[cls]


@overload
def get_config[C](name: type[C]) -> C: ...
@overload
def get_config(name: str) -> ConfigInstance: ...
def get_config(name: Any) -> Any:
    """
    Returns the registered instance of a config class, by class or by group name.

    Raises:
        KeyError: Nothing is registered under that class or name.
    """
    if isinstance(name, type):
        try:
            return _registry[_class_names[name]]
        except KeyError:
            raise KeyError(f"{name.__name__} is not a registered config class.") from None
    try:
        return _registry[name]
    except KeyError:
        raise KeyError(f"No config group named '{name}' is registered.") from None


def groups() -> dict[str, ConfigInstance]:
    """The registered instances by group name, in registration order."""
    return dict(_registry)


def save() -> None:
    """Writes every registered instance to `QSettings` and flushes to permanent storage."""
    for inst in _registry.values():
        inst.to_qsettings()
    settings().sync()


def reset(exclude: Iterable[str] | None = None) -> None:
    """Restores the defaults of every registered group except those named in `exclude`."""
    skip = set(exclude or ())
    for name, inst in _registry.items():
        if name not in skip:
            inst.restore_defaults()
    settings().sync()


def clean(exclude: Iterable[str] | None = None) -> None:
    """
    Deletes stored settings.

    With no `exclude`, the whole store is cleared, including groups this package never registered. Otherwise
    every top-level group not named in `exclude` is removed. Registered instances keep their in-memory values;
    call `reset` to change those.
    """
    store = settings()
    if not exclude:
        store.clear()
    else:
        skip = set(exclude)
        for name in list(store.childGroups()):
            if name not in skip:
                store.remove(name)
    store.sync()


def update_value(group: str, key: str, value: Any) -> None:
    """
    Sets one attribute of a registered group.

    Raises:
        ValueError: The group or the attribute does not exist.
    """
    try:
        inst = get_config(group)
    except KeyError as exc:
        raise ValueError(str(exc)) from exc
    if not any(f.name == key for f in _fields(type(inst))):
        raise ValueError(f"No attribute '{key}' in config group '{group}'")
    setattr(inst, key, value)


def create_snapshot() -> dict[str, dict[str, Any]]:
    """The current values of every registered group: `{group: {field: value}}`."""
    return {name: attrs.asdict(inst, recurse=False) for name, inst in _registry.items()}


def restore_snapshot(snapshot: Mapping[str, Mapping[str, Any]]) -> None:
    """Sets every value in a snapshot from `create_snapshot` and flushes to storage."""
    for group, values in snapshot.items():
        for key, value in values.items():
            update_value(group, key, value)
    settings().sync()


def iter_fields(include_hidden: bool = True) -> Iterator[FieldInfo]:
    """
    Yields one `FieldInfo` per declared setting, in declaration order.

    Use it to generate documentation or to check documentation against the declarations.
    """
    for name, inst in _registry.items():
        hidden = type(inst).__hidden__
        if hidden and not include_hidden:
            continue
        for field in _fields(type(inst)):
            editor: EditorWidgetInfo[Any] | None = field.metadata.get(EDITOR_KEY)
            yield FieldInfo(
                group=name,
                name=field.name,
                type=_field_type(field),
                default=_field_default(field),
                label=editor.label if editor is not None else None,
                description=field.metadata.get(DESCRIPTION_KEY, ""),
                hidden=hidden,
            )
