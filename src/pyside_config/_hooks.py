"""
How the editor reads, writes and watches each kind of widget.

`EditorHooks` bundles the three operations the settings dialog needs from an editor widget. `DEFAULT_HOOKS` maps
widget classes to hooks; `hooks_for` resolves a widget through its MRO, so a `QCheckBox` subclass such as
`pyside_widgets.AnimatedToggleSwitch` works without registration. Applications add their own widgets with
`register_editor_hooks`.
"""

from __future__ import annotations

from collections.abc import Callable
from operator import attrgetter, methodcaller
from typing import Any, NamedTuple

from PySide6 import QtCore, QtGui, QtWidgets
from pyside_widgets import DecimalSpinBox, EnumComboBox

type Editor = QtWidgets.QWidget | QtGui.QAction


class EditorHooks(NamedTuple):
    """
    The operations the settings dialog performs on an editor widget.

    Attributes:
        value_changed: Returns the signal that fires when the user changes the value. Its payload is ignored;
            the value is read through `get_value`.
        get_value: Returns the editor's current value.
        set_value: Shows a value in the editor.
    """

    value_changed: Callable[[Any], QtCore.SignalInstance]
    get_value: Callable[[Any], Any]
    set_value: Callable[[Any, Any], None]

    @classmethod
    def from_names(cls, value_changed: str, get_value: str, set_value: str) -> EditorHooks:
        """
        Builds hooks from a signal name and two method names.

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
    if index < 0:
        index = editor.findText(str(value))
    editor.setCurrentIndex(index)


DEFAULT_HOOKS: dict[type, EditorHooks] = {
    QtGui.QAction: EditorHooks.from_names("toggled", "isChecked", "setChecked"),
    QtWidgets.QAbstractButton: EditorHooks.from_names("toggled", "isChecked", "setChecked"),
    QtWidgets.QAbstractSlider: EditorHooks.from_names("valueChanged", "value", "setValue"),
    QtWidgets.QSpinBox: EditorHooks.from_names("valueChanged", "value", "setValue"),
    QtWidgets.QDoubleSpinBox: EditorHooks.from_names("valueChanged", "value", "setValue"),
    QtWidgets.QComboBox: EditorHooks(attrgetter("currentIndexChanged"), methodcaller("currentData"), _combo_box_set),
    QtWidgets.QFontComboBox: EditorHooks.from_names("currentFontChanged", "currentFont", "setCurrentFont"),
    QtWidgets.QLineEdit: EditorHooks.from_names("textChanged", "text", "setText"),
    QtWidgets.QPlainTextEdit: EditorHooks.from_names("textChanged", "toPlainText", "setPlainText"),
    QtWidgets.QTextEdit: EditorHooks.from_names("textChanged", "toPlainText", "setPlainText"),
    QtWidgets.QKeySequenceEdit: EditorHooks.from_names("keySequenceChanged", "keySequence", "setKeySequence"),
    QtWidgets.QDateTimeEdit: EditorHooks.from_names("dateTimeChanged", "dateTime", "setDateTime"),
    DecimalSpinBox: EditorHooks.from_names("valueChanged", "value", "setValue"),
    EnumComboBox: EditorHooks.from_names("sig_current_enum_changed", "current_enum", "set_current_enum"),
}


def register_editor_hooks(widget_type: type, hooks: EditorHooks) -> None:
    """Registers (or replaces) the hooks used for `widget_type` and its subclasses."""
    DEFAULT_HOOKS[widget_type] = hooks


def hooks_for(editor: Editor | type) -> EditorHooks:
    """
    Returns the hooks registered for the editor's class or its nearest registered base class.

    Raises:
        LookupError: No hooks are registered for any class in the MRO.
    """
    cls = editor if isinstance(editor, type) else type(editor)
    for base in cls.__mro__:
        hooks = DEFAULT_HOOKS.get(base)
        if hooks is not None:
            return hooks
    raise LookupError(
        f"No editor hooks registered for {cls.__name__}. Pass sig_value_changed, get_value_method and "
        "set_value_method to EditorWidgetInfo, or call pyside_config.register_editor_hooks()."
    )
