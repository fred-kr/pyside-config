"""
The generated settings dialog.

`create_editor` builds a tabbed `QDialog`, one tab per visible group, one `SettingCard` per field with an editor.
Edits are staged in the dialog and applied to the config instances when the user presses OK; Cancel discards them.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from PySide6 import QtCore, QtWidgets
from pyside_widgets import SettingCard

from pyside_config._core import (
    DESCRIPTION_KEY,
    EDITOR_KEY,
    ConfigInstance,
    EditorWidgetInfo,
    _field_default,
    _fields,
    _registry,
)
from pyside_config._settings import settings


def build_group_page(inst: ConfigInstance, staged: dict[str, Any] | None, **kwargs: Any) -> QtWidgets.QScrollArea:
    """
    A scroll area with one `SettingCard` per editable field of `inst`.

    With `staged=None`, every edit is written to `inst` at once. Otherwise edits are recorded in `staged`
    (`{field name: value}`) and left for the caller to apply.
    """
    container = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(container)
    layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)

    for field in _fields(type(inst)):
        info: EditorWidgetInfo[Any] | None = field.metadata.get(EDITOR_KEY)
        if info is None:
            continue

        widget = info.widget_factory(**kwargs)
        if info.widget_properties is not None:
            info.widget_properties.apply_to_widget(widget)
        hooks = info.hooks(widget)
        hooks.set_value(widget, getattr(inst, field.name))

        name = field.name
        default = _field_default(field)

        def on_changed(*_args: Any, _name: str = name, _widget: Any = widget, _hooks: Any = hooks) -> None:
            value = _hooks.get_value(_widget)
            if staged is None:
                setattr(inst, _name, value)
            else:
                staged[_name] = value

        def on_reset(_widget: Any = widget, _hooks: Any = hooks, _default: Any = default) -> None:
            _hooks.set_value(_widget, _default)

        hooks.value_changed(widget).connect(on_changed)

        card = SettingCard(
            title=info.label,
            editor_widget=widget,
            description=field.metadata.get(DESCRIPTION_KEY, ""),
            icon=info.icon,
        )
        card.sig_reset_clicked.connect(on_reset)
        layout.addWidget(card)

    scroll_area = QtWidgets.QScrollArea()
    scroll_area.setWidgetResizable(True)
    scroll_area.setWidget(container)
    return scroll_area


def create_editor(
    parent: QtWidgets.QWidget | None = None,
    exclude: Iterable[str] | None = None,
    window_title: str = "Settings",
    *,
    include_hidden: bool = False,
) -> QtWidgets.QDialog:
    """
    A modal dialog with one tab per registered group.

    Edits are applied when the dialog is accepted and dropped when it is rejected, so callers need no snapshot.
    Each applied change emits `signals().sig_value_changed`; the store is flushed once at the end.

    Args:
        parent: Parent widget of the dialog.
        exclude: Group names to leave out.
        window_title: Title of the dialog window.
        include_hidden: Also show groups declared with `hidden=True`.
    """
    dlg = QtWidgets.QDialog(parent)
    dlg.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
    dlg.setModal(True)
    dlg.setWindowTitle(window_title)

    skip = set(exclude or ())
    pending: list[tuple[ConfigInstance, dict[str, Any]]] = []

    tab_widget = QtWidgets.QTabWidget()
    for name, inst in _registry.items():
        if name in skip or (type(inst).__hidden__ and not include_hidden):
            continue
        staged: dict[str, Any] = {}
        pending.append((inst, staged))
        tab_widget.addTab(build_group_page(inst, staged), name)

    def apply() -> None:
        for inst, staged in pending:
            for key, value in staged.items():
                setattr(inst, key, value)
        settings().sync()

    dlg.accepted.connect(apply)

    btn_box = QtWidgets.QDialogButtonBox(
        QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel
    )
    btn_box.accepted.connect(dlg.accept)
    btn_box.rejected.connect(dlg.reject)

    layout = QtWidgets.QVBoxLayout(dlg)
    layout.addWidget(tab_widget)
    layout.addWidget(btn_box)
    dlg.resize(800, 600)
    return dlg
