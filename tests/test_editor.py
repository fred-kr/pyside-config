import enum
from typing import Any, cast

import pytest
from PySide6 import QtCore, QtWidgets
from pyside_widgets import AnimatedToggleSwitch, EnumComboBox, SettingCard

import pyside_config as qconfig
from pyside_config import ConfigInstance, EditorWidgetInfo, _core, config, config_field, get_config, hooks_for
from pyside_config.helpers import make_combo_box_info, make_line_edit_info, make_spin_box_info


class Method(enum.StrEnum):
    Fast = "fast"
    Slow = "slow"


def enum_combo() -> EnumComboBox[Method]:
    combo: EnumComboBox[Method] = EnumComboBox()
    combo.set_enum_class(Method)
    return combo


def plain_combo() -> QtWidgets.QComboBox:
    combo = QtWidgets.QComboBox()
    combo.addItem("Ten", 10)
    combo.addItem("Twenty", 20)
    return combo


@config(group_name="Editable", register=False)
class Editable:
    count: int = config_field(default=3, editor=make_spin_box_info("Count", minimum=0, maximum=10, suffix=" px"))
    name: str = config_field(default="a", editor=make_line_edit_info("Name"))
    flag: bool = config_field(default=False, editor=EditorWidgetInfo("Flag", AnimatedToggleSwitch))
    method: Method = config_field(default=Method.Fast, editor=EditorWidgetInfo("Method", enum_combo))
    choice: int = config_field(default=10, editor=make_combo_box_info("Choice", plain_combo))
    internal: str = config_field(default="not shown")


@config(group_name="Hidden", hidden=True, register=False)
class Hidden:
    secret: int = config_field(default=1, editor=make_spin_box_info("Secret"))


@pytest.fixture
def cfg() -> Editable:
    """Registers both groups into the (fresh) registry and returns the `Editable` instance."""
    _core._register(cast(type[ConfigInstance], Editable))
    _core._register(cast(type[ConfigInstance], Hidden))
    return get_config(Editable)


def cards(root: QtWidgets.QWidget) -> dict[str, SettingCard]:
    return {card.get_title(): card for card in root.findChildren(SettingCard)}


def editor[W: QtWidgets.QWidget](root: QtWidgets.QWidget, title: str, cls: type[W]) -> W:
    widget = cards(root)[title].editor_widget
    assert isinstance(widget, cls)
    return widget


def tab_titles(dlg: QtWidgets.QDialog) -> list[str]:
    tabs = dlg.findChild(QtWidgets.QTabWidget)
    assert isinstance(tabs, QtWidgets.QTabWidget)
    return [tabs.tabText(i) for i in range(tabs.count())]


def test_dialog_shows_visible_groups_only(qtbot: Any, cfg: Editable) -> None:
    dlg = qconfig.create_editor()
    qtbot.addWidget(dlg)
    assert tab_titles(dlg) == ["Editable"]
    assert set(cards(dlg)) == {"Count", "Name", "Flag", "Method", "Choice"}

    dlg_all = qconfig.create_editor(include_hidden=True, exclude=["Editable"])
    qtbot.addWidget(dlg_all)
    assert tab_titles(dlg_all) == ["Hidden"]


def test_editors_show_current_values_and_properties(qtbot: Any, cfg: Editable) -> None:
    cfg.count = 7
    cfg.method = Method.Slow
    cfg.choice = 20
    dlg = qconfig.create_editor()
    qtbot.addWidget(dlg)
    spin = editor(dlg, "Count", QtWidgets.QSpinBox)
    assert spin.value() == 7 and spin.maximum() == 10 and spin.suffix() == " px"
    assert editor(dlg, "Method", EnumComboBox).current_enum() == Method.Slow
    assert editor(dlg, "Choice", QtWidgets.QComboBox).currentData() == 20
    assert editor(dlg, "Flag", AnimatedToggleSwitch).isChecked() is False


def test_edits_are_staged_until_ok(qtbot: Any, cfg: Editable, fresh_store: QtCore.QSettings) -> None:
    received: list[tuple[str, object]] = []
    qconfig.signals().sig_value_changed.connect(lambda g, k, v: received.append((k, v)))

    dlg = qconfig.create_editor()
    qtbot.addWidget(dlg)
    editor(dlg, "Count", QtWidgets.QSpinBox).setValue(9)
    editor(dlg, "Name", QtWidgets.QLineEdit).setText("zed")
    editor(dlg, "Flag", AnimatedToggleSwitch).setChecked(True)
    editor(dlg, "Method", EnumComboBox).set_current_enum(Method.Slow)
    editor(dlg, "Choice", QtWidgets.QComboBox).setCurrentIndex(1)

    assert (cfg.count, cfg.name, cfg.flag, cfg.method) == (3, "a", False, Method.Fast)
    assert received == [] and fresh_store.allKeys() == []

    dlg.accept()
    qconfig.signals().sig_value_changed.disconnect()

    assert (cfg.count, cfg.name, cfg.flag, cfg.method, cfg.choice) == (9, "zed", True, Method.Slow, 20)
    assert cfg.method is Method.Slow  # the widget's plain str was coerced back to the member
    assert dict(received) == {"count": 9, "name": "zed", "flag": True, "method": Method.Slow, "choice": 20}
    assert fresh_store.value("Editable/count") == 9


def test_cancel_discards_edits(qtbot: Any, cfg: Editable, fresh_store: QtCore.QSettings) -> None:
    dlg = qconfig.create_editor()
    qtbot.addWidget(dlg)
    editor(dlg, "Count", QtWidgets.QSpinBox).setValue(9)
    dlg.reject()
    assert cfg.count == 3
    assert fresh_store.allKeys() == []


def test_reset_button_stages_default(qtbot: Any, cfg: Editable) -> None:
    cfg.count = 8
    dlg = qconfig.create_editor()
    qtbot.addWidget(dlg)
    cards(dlg)["Count"].btn_reset.click()
    assert editor(dlg, "Count", QtWidgets.QSpinBox).value() == 3
    assert cfg.count == 8
    dlg.accept()
    assert cfg.count == 3


def test_instance_editor_applies_immediately(qtbot: Any, cfg: Editable) -> None:
    page = cast(ConfigInstance, cfg).create_editor()
    qtbot.addWidget(page)
    editor(page, "Count", QtWidgets.QSpinBox).setValue(6)
    assert cfg.count == 6


def test_hooks_resolution() -> None:
    assert hooks_for(AnimatedToggleSwitch) is qconfig.DEFAULT_HOOKS[QtWidgets.QAbstractButton]
    assert hooks_for(EnumComboBox) is qconfig.DEFAULT_HOOKS[EnumComboBox]
    with pytest.raises(LookupError):
        hooks_for(QtWidgets.QLabel)


def test_explicit_names_override_hooks(qtbot: Any) -> None:
    info = EditorWidgetInfo("Text", QtWidgets.QLineEdit, "editingFinished", "setText", "text")
    edit = QtWidgets.QLineEdit()
    qtbot.addWidget(edit)
    hooks = info.hooks(edit)
    hooks.set_value(edit, "abc")
    assert hooks.get_value(edit) == "abc"
    assert hooks.value_changed(edit) == edit.editingFinished
