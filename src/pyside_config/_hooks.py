"""
How the settings dialog reads, writes and watches an editor widget.

`EditorHooks` bundles the three operations. By default they come from the widget's Qt USER property, the same
property `QDataWidgetMapper` and item delegates use: `value` for a `QSpinBox`, `text` for a `QLineEdit`, `checked`
for a `QCheckBox`. A widget whose USER property is not the value to store gets hooks registered for its class with
`register_editor_hooks`. The package registers three: `QComboBox` (item data, not text), `QFontComboBox` (a
`QFont`) and `QTextEdit` (plain text, not HTML).
"""

from __future__ import annotations

from collections.abc import Callable
from operator import attrgetter, methodcaller
from typing import Any, NamedTuple

import shiboken6
from PySide6 import QtCore, QtWidgets

from pyside_config._settings import to_storable


class EditorHooks(NamedTuple):
    """
    The operations the settings dialog performs on an editor widget.

    Attributes:
        value_changed: Returns the signal that fires when the user changes the value. Its payload is ignored;
            the value is read through `get_value`.
        get_value: Returns the editor's current value.
        set_value: Shows a value in the editor. It receives the storable form of the field's value: an enum
            member as its `.value`, a `Path` or `Decimal` as `str`.
    """

    value_changed: Callable[[Any], QtCore.SignalInstance]
    get_value: Callable[[Any], Any]
    set_value: Callable[[Any, Any], None]

    @classmethod
    def from_names(cls, value_changed: str, get_value: str, set_value: str) -> EditorHooks:
        """
        Builds hooks from a signal name, a getter name and a setter name.

        Example:
            ```python
            EditorHooks.from_names("valueChanged", "value", "setValue")
            ```
        """
        return cls(
            attrgetter(value_changed),
            methodcaller(get_value),
            lambda editor, value: getattr(editor, set_value)(value),
        )


def _combo_box_set(editor: QtWidgets.QComboBox, value: Any) -> None:
    index = editor.findData(value)
    if index < 0:  # item data that Qt cannot compare, such as members of a plain Enum
        index = next((i for i in range(editor.count()) if to_storable(editor.itemData(i)) == value), -1)
    if index < 0:
        index = editor.findText(str(value))
    editor.setCurrentIndex(index)


_registered: dict[type[QtWidgets.QWidget], EditorHooks] = {
    QtWidgets.QComboBox: EditorHooks(attrgetter("currentIndexChanged"), methodcaller("currentData"), _combo_box_set),
    QtWidgets.QFontComboBox: EditorHooks.from_names("currentFontChanged", "currentFont", "setCurrentFont"),
    QtWidgets.QTextEdit: EditorHooks.from_names("textChanged", "toPlainText", "setPlainText"),
}


def register_editor_hooks(widget_type: type[QtWidgets.QWidget], hooks: EditorHooks) -> None:
    """
    Registers (or replaces) the hooks used for `widget_type` and its subclasses.

    A subclass that declares a USER property of its own keeps using that property; see `hooks_for`.

    Example:
        ```python
        register_editor_hooks(ColorButton, EditorHooks.from_names("colorChanged", "color", "setColor"))
        ```
    """
    _registered[widget_type] = hooks


def hooks_for(editor: QtWidgets.QWidget) -> EditorHooks:
    """
    The hooks for `editor`.

    The class nearest to the editor's own class wins: hooks registered for a class in its MRO, or a USER property
    declared by a subclass of that class. `EnumComboBox` therefore uses its `currentEnum` property although it is a
    `QComboBox`. A USER property counts only if it is writable and has a notify signal.

    Raises:
        LookupError: The editor has neither registered hooks nor a usable USER property.
    """
    registered_type = next((base for base in type(editor).__mro__ if base in _registered), None)
    meta = _meta_object(editor)
    prop = meta.userProperty()
    if prop.isValid() and prop.isWritable() and prop.hasNotifySignal():
        if registered_type is None or _declared_below(meta, prop, registered_type):
            return _user_property_hooks(prop)
    if registered_type is not None:
        return _registered[registered_type]
    raise LookupError(
        f"{type(editor).__name__} has no writable USER property with a notify signal and no registered hooks. "
        "Pass hooks=EditorHooks(...) to config_field, or call pyside_config.register_editor_hooks()."
    )


def _meta_object(editor: QtWidgets.QWidget) -> QtCore.QMetaObject:
    """
    The meta-object of the editor's class.

    Taken from the class, not from `editor.metaObject()`: PySide ties the object that method returns to the widget
    and invalidates `Class.staticMetaObject` for the whole process once the widget is destroyed. If other code
    already caused that, the instance's meta-object is the only one left.
    """
    meta: QtCore.QMetaObject = type(editor).staticMetaObject  # pyright: ignore[reportAttributeAccessIssue]
    return meta if shiboken6.isValid(meta) else editor.metaObject()


def _declared_below(meta: QtCore.QMetaObject, prop: QtCore.QMetaProperty, base: type[QtWidgets.QWidget]) -> bool:
    """Whether `prop` is declared by a proper subclass of `base`. Classes are matched by name."""
    while meta.propertyOffset() > prop.propertyIndex():
        meta = meta.superClass()
    ancestor = meta.superClass()
    while ancestor is not None:
        if ancestor.className() == base.__name__:
            return True
        ancestor = ancestor.superClass()
    return False


def _user_property_hooks(prop: QtCore.QMetaProperty) -> EditorHooks:
    raw_name = prop.name()  # str at runtime, bytes according to the PySide6 stubs
    name = raw_name if isinstance(raw_name, str) else bytes(raw_name).decode()
    signal_name = bytes(prop.notifySignal().name().data()).decode()

    def set_value(editor: QtWidgets.QWidget, value: Any) -> None:
        if not editor.setProperty(name, value):
            raise TypeError(f"{type(editor).__name__}.{name} does not accept {value!r}")

    return EditorHooks(attrgetter(signal_name), methodcaller("property", name), set_value)
