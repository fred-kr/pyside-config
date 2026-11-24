"""
The generated settings widgets.

`GroupPage` shows one settings group: a `SettingCard` per field that has an editor. `SettingsDialog` puts one page
per visible group into tabs and adds OK, Cancel, Apply and Restore Defaults. Edits stay in the editor widgets until
they are applied. Applying validates every edited value first and changes nothing if one of them is invalid.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any
from warnings import deprecated

import attrs
from PySide6 import QtCore, QtWidgets
from pyside_widgets import SettingCard

from pyside_config._core import (
    GroupInfo,
    default_value,
    editable_fields,
    field_label,
    field_meta,
    get_config,
    group_info,
    groups,
    prepare_value,
    signals,
    sync,
    values_equal,
)
from pyside_config._hooks import hooks_for
from pyside_config._settings import to_storable


class _FieldEditor(QtCore.QObject):
    """Connects one field of a config instance to its editor widget and its card."""

    sig_edited = QtCore.Signal()
    """Emitted when the user changed the editor's value, including through the card's reset button."""

    def __init__(self, inst: Any, field: attrs.Attribute[Any], parent: QtCore.QObject) -> None:
        super().__init__(parent)
        meta = field_meta(field)
        if meta.editor is None:
            raise ValueError(f"Field '{field.name}' has no editor.")
        self._inst = inst
        self._field = field
        self._description = meta.description
        self._loading = False
        self.edited = False

        self.widget = meta.editor()
        if not isinstance(self.widget, QtWidgets.QWidget):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise TypeError(f"The editor of '{field.name}' returned {type(self.widget).__name__}, not a QWidget.")
        self._hooks = meta.hooks or hooks_for(self.widget)
        self.card = SettingCard(
            title=field_label(field), editor_widget=self.widget, description=meta.description, icon=meta.icon
        )

        self.revert()
        self._hooks.value_changed(self.widget).connect(self._on_widget_changed)
        self.card.sig_reset_clicked.connect(self.show_default)

    def value(self) -> Any:
        """The editor's value in the field's type. Raises what the field's coercion, converter or validator raises."""
        return prepare_value(self._inst, self._field, self._hooks.get_value(self.widget))

    def is_modified(self) -> bool:
        """Whether the user edited the value and it differs from the instance's, or is invalid."""
        if not self.edited:
            return False
        try:
            return not values_equal(self.value(), getattr(self._inst, self._field.name))
        except Exception:
            return True

    def validate(self) -> bool:
        """Checks the editor's value. An invalid value replaces the card's description by the error message."""
        try:
            self.value()
        except Exception as exc:
            self.card.set_description(self.tr("Invalid value: {0}").format(exc))
            return False
        self.card.set_description(self._description)
        return True

    def apply(self) -> None:
        """Assigns a modified value to the instance, then shows what the instance holds."""
        if self.is_modified():
            setattr(self._inst, self._field.name, self.value())
        self.revert()

    def revert(self) -> None:
        """Shows the instance's value and forgets the user's edit."""
        self._loading = True
        try:
            self._show(getattr(self._inst, self._field.name))
        finally:
            self._loading = False
        self.edited = False
        self.card.set_description(self._description)

    @QtCore.Slot()
    def show_default(self) -> None:
        """Shows the field's default as if the user had entered it."""
        self._show(default_value(self._inst, self._field))

    def _show(self, value: Any) -> None:
        self._hooks.set_value(self.widget, to_storable(value))

    @QtCore.Slot()
    def _on_widget_changed(self) -> None:
        if self._loading:
            return
        self.edited = True
        self.validate()
        self.sig_edited.emit()


class GroupPage(QtWidgets.QWidget):
    """
    The editors of one settings group, in a scroll area.

    Each field declared with an `editor` gets a `SettingCard` with the editor widget, the label, the description
    and a reset button. Edits stay in the widgets until `apply` assigns them to the config instance. An editor
    the user has not touched follows changes made to the instance elsewhere.

    Use it to embed a group in your own window; `SettingsDialog` is built from these pages.

    Example:
        ```python
        page = GroupPage(PlotConfig)
        page.sig_modified.connect(apply_button.setEnabled)
        apply_button.clicked.connect(page.apply)
        ```
    """

    sig_modified = QtCore.Signal(bool)
    """Emitted with `is_modified()` after an edit, `apply`, `revert` or `restore_defaults`."""

    def __init__(self, group: type | str, parent: QtWidgets.QWidget | None = None) -> None:
        """
        Args:
            group: A registered config class or its group name.
            parent: Parent widget.

        Raises:
            KeyError: The group is not registered.
            LookupError: An editor widget has no USER property and no registered hooks.
        """
        super().__init__(parent)
        self._info = group_info(group)
        inst = get_config(self._info.name)

        container = QtWidgets.QWidget()
        cards = QtWidgets.QVBoxLayout(container)
        cards.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)

        self._editors: dict[str, _FieldEditor] = {}
        for field in editable_fields(self._info.config_class):
            editor = _FieldEditor(inst, field, self)
            editor.sig_edited.connect(self._emit_modified)
            cards.addWidget(editor.card)
            self._editors[field.name] = editor

        scroll_area = QtWidgets.QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll_area.setWidget(container)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(scroll_area)

        signals().sig_value_changed.connect(self._on_value_changed)

    def group(self) -> GroupInfo:
        """The group this page edits."""
        return self._info

    def editor_widget(self, name: str) -> QtWidgets.QWidget:
        """
        The editor widget of the field called `name`.

        Raises:
            KeyError: The group has no field of that name with an editor.
        """
        return self._editors[name].widget

    def values(self) -> dict[str, Any]:
        """
        The values currently shown, by field name, in the fields' types.

        Raises:
            ValueError, TypeError: An editor holds a value its field rejects. Call `validate` first.
        """
        return {name: editor.value() for name, editor in self._editors.items()}

    def is_modified(self) -> bool:
        """Whether applying would change at least one value, or an edited value is invalid."""
        return any(editor.is_modified() for editor in self._editors.values())

    def validate(self) -> bool:
        """
        Checks every editor against its field's type, converter and validators.

        Each invalid editor shows the error in place of its description. Returns whether all values are valid.
        """
        results = [editor.validate() for editor in self._editors.values()]
        return all(results)

    @QtCore.Slot(result=bool)
    def apply(self) -> bool:
        """
        Assigns the edited values to the config instance.

        Nothing is assigned unless every value is valid. Each changed field emits `sig_value_changed`. The store
        is not flushed; call `pyside_config.sync()`. Returns whether the values were applied.
        """
        if not self.validate():
            return False
        for editor in self._editors.values():
            editor.apply()
        self._emit_modified()
        return True

    @QtCore.Slot()
    def revert(self) -> None:
        """Drops the edits and shows the config instance's values."""
        for editor in self._editors.values():
            editor.revert()
        self._emit_modified()

    @QtCore.Slot()
    def restore_defaults(self) -> None:
        """Shows every field's default. Like any other edit, the defaults are only assigned by `apply`."""
        for editor in self._editors.values():
            editor.show_default()
        self._emit_modified()

    @QtCore.Slot()
    def _emit_modified(self) -> None:
        self.sig_modified.emit(self.is_modified())

    @QtCore.Slot(str, str, object)
    def _on_value_changed(self, group: str, name: str, value: object) -> None:
        editor = self._editors.get(name) if group == self._info.name else None
        if editor is not None and not editor.edited:
            editor.revert()


class SettingsDialog(QtWidgets.QDialog):
    """
    A dialog with one tab per settings group and the buttons OK, Cancel, Apply and Restore Defaults.

    OK and Apply validate every page, assign the edited values and flush the store. If a value is invalid, nothing
    is assigned, the tab with the error is shown and the dialog stays open. Cancel discards the edits. Restore
    Defaults shows the defaults of the current tab; they are assigned by OK or Apply like any other edit.

    The dialog sets neither modality, size nor `WA_DeleteOnClose`. Choose them where you show it.

    Example:
        ```python
        dialog = SettingsDialog(main_window)
        dialog.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.open()
        ```
    """

    def __init__(
        self,
        parent: QtWidgets.QWidget | None = None,
        *,
        exclude: Iterable[type | str] = (),
        include_hidden: bool = False,
    ) -> None:
        """
        Args:
            parent: Parent widget.
            exclude: Config classes or group names to leave out.
            include_hidden: Also show groups declared with `hidden=True`.

        Raises:
            KeyError: An excluded group is not registered.
        """
        super().__init__(parent)
        self.setWindowTitle(self.tr("Settings"))

        skip = {group_info(group).name for group in exclude}
        self._tabs = QtWidgets.QTabWidget(self)
        self._pages: list[GroupPage] = []
        for info in groups():
            if info.name in skip or (info.hidden and not include_hidden):
                continue
            if not editable_fields(info.config_class):
                continue
            page = GroupPage(info.name, self)
            page.sig_modified.connect(self._update_buttons)
            self._tabs.addTab(page, info.title)
            self._pages.append(page)

        buttons = QtWidgets.QDialogButtonBox.StandardButton
        self._button_box = QtWidgets.QDialogButtonBox(
            buttons.Ok | buttons.Cancel | buttons.Apply | buttons.RestoreDefaults, self
        )
        self._button_box.accepted.connect(self.accept)
        self._button_box.rejected.connect(self.reject)
        self._button_box.button(buttons.Apply).clicked.connect(self.apply)
        self._button_box.button(buttons.RestoreDefaults).clicked.connect(self.restore_defaults)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self._tabs)
        layout.addWidget(self._button_box)
        self._update_buttons()

    def pages(self) -> list[GroupPage]:
        """The pages, in tab order."""
        return list(self._pages)

    def button_box(self) -> QtWidgets.QDialogButtonBox:
        """The dialog's button box, for adding buttons or changing their texts."""
        return self._button_box

    def is_modified(self) -> bool:
        """Whether any page holds an edit that applying would assign."""
        return any(page.is_modified() for page in self._pages)

    @QtCore.Slot(result=bool)
    def apply(self) -> bool:
        """
        Validates every page, assigns the edited values and flushes the store.

        Returns `False` and assigns nothing if a value is invalid; the first tab with an error becomes current.
        """
        invalid = [page for page in self._pages if not page.validate()]
        if invalid:
            self._tabs.setCurrentWidget(invalid[0])
            return False
        for page in self._pages:
            page.apply()
        sync()
        self._update_buttons()
        return True

    @QtCore.Slot()
    def restore_defaults(self) -> None:
        """Shows the defaults of the current tab's fields without assigning them."""
        page = self._tabs.currentWidget()
        if isinstance(page, GroupPage):
            page.restore_defaults()

    @QtCore.Slot()
    def accept(self) -> None:
        """Applies the edits and closes the dialog. Stays open if a value is invalid."""
        if self.apply():
            super().accept()

    @QtCore.Slot()
    def _update_buttons(self) -> None:
        self._button_box.button(QtWidgets.QDialogButtonBox.StandardButton.Apply).setEnabled(self.is_modified())


@deprecated("create_editor() is replaced by SettingsDialog. Removed in 0.4.")
def create_editor(
    parent: QtWidgets.QWidget | None = None,
    exclude: Iterable[str] | None = None,
    window_title: str = "Settings",
    *,
    include_hidden: bool = False,
) -> SettingsDialog:
    """Deprecated. A `SettingsDialog` that is modal, 800x600 and deleted when closed, as in 0.2."""
    dialog = SettingsDialog(parent, exclude=exclude or (), include_hidden=include_hidden)
    dialog.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
    dialog.setModal(True)
    dialog.setWindowTitle(window_title)
    dialog.resize(800, 600)
    return dialog
