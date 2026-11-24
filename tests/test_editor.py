import decimal
import enum
from pathlib import Path
from typing import Any, cast

import attrs
import pytest
import shiboken6
from PySide6 import QtCore, QtWidgets
from pyside_widgets import AnimatedToggleSwitch, DecimalSpinBox, EnumComboBox, SettingCard

import pyside_config as qconfig
from pyside_config import EditorHooks, GroupPage, SettingsDialog, config, config_field, get_config
from pyside_config._hooks import hooks_for

type Changes = list[tuple[str, str, object]]

Buttons = QtWidgets.QDialogButtonBox.StandardButton


class Method(enum.StrEnum):
    Fast = "fast"
    Slow = "slow"


class Shape(enum.Enum):  # members that Qt cannot store as a plain value
    Round = ("round", 0)
    Square = ("square", 4)


def enum_combo() -> EnumComboBox[Method]:
    return EnumComboBox(enum_class=Method)


def plain_combo() -> QtWidgets.QComboBox:
    combo = QtWidgets.QComboBox()
    combo.addItem("Ten", 10)
    combo.addItem("Twenty", 20)
    return combo


def shape_combo() -> QtWidgets.QComboBox:
    combo = QtWidgets.QComboBox()
    for member in Shape:
        combo.addItem(member.name, member)
    return combo


def offset_spin_box() -> QtWidgets.QSpinBox:
    box = QtWidgets.QSpinBox()
    box.setRange(-100, 100)
    return box


@pytest.fixture
def cfg(qtbot: Any) -> Any:
    """Declares the groups `Editable`, `Second` and the hidden `Hidden`; returns the `Editable` instance."""

    @config(group="Editable", title="Editable settings")
    class Editable:
        count: int = config_field(
            default=3, label="Count", editor=lambda: QtWidgets.QSpinBox(minimum=0, maximum=10, suffix=" px")
        )
        name: str = config_field(default="a", description="A name", editor=QtWidgets.QLineEdit)
        flag: bool = config_field(default=False, editor=AnimatedToggleSwitch)
        method: Method = config_field(default=Method.Fast, editor=enum_combo)
        choice: int = config_field(default=10, editor=plain_combo)
        shape: Shape = config_field(default=Shape.Round, editor=shape_combo)
        offset: int = config_field(default=0, editor=offset_spin_box)
        limited: int = config_field(
            default=1,
            description="At most 10",
            editor=lambda: QtWidgets.QSpinBox(maximum=100),
            validator=attrs.validators.le(10),
        )
        folder: Path = config_field(default=Path("c:/data"), editor=QtWidgets.QLineEdit)
        ratio: decimal.Decimal = config_field(default=decimal.Decimal("0.5"), editor=DecimalSpinBox)
        shouted: str = config_field(default="x", converter=str.upper, editor=QtWidgets.QLineEdit)
        internal: str = config_field(default="not shown")

    @config(group="Second")
    class Second:
        size: int = config_field(default=5, editor=QtWidgets.QSpinBox)

    @config(group="Hidden", hidden=True)
    class Hidden:
        secret: int = config_field(default=1, editor=QtWidgets.QSpinBox)

    @config(group="NoEditors")
    class NoEditors:
        state: str = config_field(default="")

    return get_config(Editable)


def dialog(qtbot: Any, **kwargs: Any) -> SettingsDialog:
    dlg = SettingsDialog(**kwargs)
    qtbot.addWidget(dlg)
    return dlg


def page(dlg: SettingsDialog, group: str = "Editable") -> GroupPage:
    return next(p for p in dlg.pages() if p.group().name == group)


def editor[W: QtWidgets.QWidget](dlg: SettingsDialog, name: str, cls: type[W], group: str = "Editable") -> W:
    widget = page(dlg, group).editor_widget(name)
    assert isinstance(widget, cls)
    return widget


def card(dlg: SettingsDialog, name: str) -> SettingCard:
    widget: QtCore.QObject | None = page(dlg).editor_widget(name)
    while widget is not None and not isinstance(widget, SettingCard):
        widget = widget.parent()
    assert widget is not None
    return widget


def tab_titles(dlg: SettingsDialog) -> list[str]:
    tabs = dlg.findChild(QtWidgets.QTabWidget)
    assert isinstance(tabs, QtWidgets.QTabWidget)
    return [tabs.tabText(i) for i in range(tabs.count())]


# --- which groups and fields are shown ----------------------------------------------------------------------------


def test_dialog_shows_visible_groups_with_editors(qtbot: Any, cfg: Any) -> None:
    dlg = dialog(qtbot)
    assert tab_titles(dlg) == ["Editable settings", "Second"]  # the title, not the storage key
    titles = {c.get_title() for c in page(dlg).findChildren(SettingCard)}
    assert titles == {
        "Count",
        "Name",
        "Flag",
        "Method",
        "Choice",
        "Shape",
        "Offset",
        "Limited",
        "Folder",
        "Ratio",
        "Shouted",
    }
    assert card(dlg, "name").get_description() == "A name"

    assert tab_titles(dialog(qtbot, include_hidden=True, exclude=["Editable"])) == ["Second", "Hidden"]
    assert tab_titles(dialog(qtbot, exclude=[qconfig.group_info("Second").config_class])) == ["Editable settings"]
    with pytest.raises(KeyError):
        SettingsDialog(exclude=["Nope"])


def test_dialog_leaves_window_behavior_to_the_caller(qtbot: Any, cfg: Any) -> None:
    dlg = dialog(qtbot)
    assert not dlg.isModal()
    assert not dlg.testAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
    assert dlg.windowTitle() == "Settings"


def test_editors_show_current_values_and_keep_their_own_properties(qtbot: Any, cfg: Any) -> None:
    cfg.count = 7
    cfg.method = Method.Slow
    cfg.choice = 20
    cfg.shape = Shape.Square
    cfg.offset = -5
    dlg = dialog(qtbot)

    spin = editor(dlg, "count", QtWidgets.QSpinBox)
    assert (spin.value(), spin.maximum(), spin.suffix()) == (7, 10, " px")
    assert spin.hasFrame()  # nothing but the factory configures the widget
    assert editor(dlg, "method", EnumComboBox).get_current_enum() is Method.Slow
    assert editor(dlg, "choice", QtWidgets.QComboBox).currentData() == 20
    assert editor(dlg, "shape", QtWidgets.QComboBox).currentText() == "Square"
    assert editor(dlg, "flag", AnimatedToggleSwitch).isChecked() is False

    offset = editor(dlg, "offset", QtWidgets.QSpinBox)
    assert (offset.minimum(), offset.maximum(), offset.value()) == (-100, 100, -5)

    assert editor(dlg, "folder", QtWidgets.QLineEdit).text() == str(Path("c:/data"))
    assert editor(dlg, "ratio", DecimalSpinBox).value() == decimal.Decimal("0.5")


# --- applying and discarding --------------------------------------------------------------------------------------


def test_edits_stay_in_the_dialog_until_ok(
    qtbot: Any, cfg: Any, fresh_store: QtCore.QSettings, changes: Changes
) -> None:
    dlg = dialog(qtbot)
    editor(dlg, "count", QtWidgets.QSpinBox).setValue(9)
    editor(dlg, "name", QtWidgets.QLineEdit).setText("zed")
    editor(dlg, "flag", AnimatedToggleSwitch).setChecked(True)
    editor(dlg, "method", EnumComboBox).set_current_enum(Method.Slow)
    editor(dlg, "choice", QtWidgets.QComboBox).setCurrentIndex(1)
    editor(dlg, "shape", QtWidgets.QComboBox).setCurrentIndex(1)
    editor(dlg, "folder", QtWidgets.QLineEdit).setText("d:/out")
    editor(dlg, "ratio", DecimalSpinBox).setValue("0.25")
    editor(dlg, "shouted", QtWidgets.QLineEdit).setText("abc")

    assert (cfg.count, cfg.name, cfg.flag, cfg.method) == (3, "a", False, Method.Fast)
    assert changes == [] and fresh_store.allKeys() == []

    dlg.accept()

    assert dlg.result() == QtWidgets.QDialog.DialogCode.Accepted
    assert (cfg.count, cfg.name, cfg.flag, cfg.choice) == (9, "zed", True, 20)
    assert cfg.method is Method.Slow  # the widget's plain str was coerced back to the member
    assert cfg.shape is Shape.Square
    assert cfg.folder == Path("d:/out")
    assert cfg.ratio == decimal.Decimal("0.25")
    assert cfg.shouted == "ABC"
    assert {name: value for _, name, value in changes} == {
        "count": 9,
        "name": "zed",
        "flag": True,
        "method": Method.Slow,
        "choice": 20,
        "shape": Shape.Square,
        "folder": Path("d:/out"),
        "ratio": decimal.Decimal("0.25"),
        "shouted": "ABC",
    }
    assert fresh_store.value("Editable/count") == 9
    assert "Editable/offset" not in fresh_store.allKeys()  # untouched fields are not written


def test_cancel_discards_edits(qtbot: Any, cfg: Any, fresh_store: QtCore.QSettings, changes: Changes) -> None:
    dlg = dialog(qtbot)
    editor(dlg, "count", QtWidgets.QSpinBox).setValue(9)
    dlg.reject()
    assert cfg.count == 3
    assert fresh_store.allKeys() == [] and changes == []


def test_apply_button_follows_the_modified_state(qtbot: Any, cfg: Any) -> None:
    dlg = dialog(qtbot)
    apply_button = dlg.button_box().button(Buttons.Apply)
    spin = editor(dlg, "count", QtWidgets.QSpinBox)
    assert not apply_button.isEnabled() and not dlg.is_modified()

    spin.setValue(9)
    assert apply_button.isEnabled() and dlg.is_modified()
    spin.setValue(3)  # back to the stored value: nothing to apply
    assert not apply_button.isEnabled()

    spin.setValue(8)
    apply_button.click()
    assert cfg.count == 8
    assert not apply_button.isEnabled()
    assert dlg.result() != QtWidgets.QDialog.DialogCode.Accepted  # Apply leaves the dialog open


def test_invalid_value_blocks_ok_and_applies_nothing(qtbot: Any, cfg: Any, changes: Changes) -> None:
    dlg = dialog(qtbot)
    editor(dlg, "size", QtWidgets.QSpinBox, group="Second").setValue(7)
    editor(dlg, "count", QtWidgets.QSpinBox).setValue(9)
    limited = editor(dlg, "limited", QtWidgets.QSpinBox)
    limited.setValue(50)
    tabs = dlg.findChild(QtWidgets.QTabWidget)
    assert isinstance(tabs, QtWidgets.QTabWidget)
    tabs.setCurrentIndex(1)

    dlg.accept()

    assert dlg.result() != QtWidgets.QDialog.DialogCode.Accepted
    assert (cfg.count, cfg.limited, get_config("Second").size) == (3, 1, 5)
    assert changes == []
    assert tabs.currentWidget() is page(dlg)  # the tab with the error is shown
    assert "must be <= 10" in card(dlg, "limited").get_description()

    limited.setValue(10)
    assert card(dlg, "limited").get_description() == "At most 10"
    dlg.accept()
    assert dlg.result() == QtWidgets.QDialog.DialogCode.Accepted
    assert (cfg.count, cfg.limited, get_config("Second").size) == (9, 10, 7)


def test_card_reset_button_shows_the_default_without_assigning_it(qtbot: Any, cfg: Any) -> None:
    cfg.count = 8
    dlg = dialog(qtbot)
    card(dlg, "count").btn_reset.click()
    assert editor(dlg, "count", QtWidgets.QSpinBox).value() == 3
    assert cfg.count == 8
    dlg.accept()
    assert cfg.count == 3


def test_restore_defaults_button_acts_on_the_current_tab(qtbot: Any, cfg: Any) -> None:
    second = get_config("Second")
    cfg.count = 8
    cfg.name = "changed"
    second.size = 9
    dlg = dialog(qtbot)

    dlg.button_box().button(Buttons.RestoreDefaults).click()
    assert editor(dlg, "count", QtWidgets.QSpinBox).value() == 3
    assert editor(dlg, "name", QtWidgets.QLineEdit).text() == "a"
    assert editor(dlg, "size", QtWidgets.QSpinBox, group="Second").value() == 9
    assert (cfg.count, cfg.name) == (8, "changed")

    dlg.accept()
    assert (cfg.count, cfg.name, second.size) == (3, "a", 9)


def test_untouched_editor_follows_changes_made_elsewhere(qtbot: Any, cfg: Any) -> None:
    dlg = dialog(qtbot)
    count = editor(dlg, "count", QtWidgets.QSpinBox)
    name = editor(dlg, "name", QtWidgets.QLineEdit)
    name.setText("typed")

    cfg.count = 6
    cfg.name = "from code"
    assert count.value() == 6
    assert name.text() == "typed"  # the user's edit is kept

    dlg.accept()
    assert (cfg.count, cfg.name) == (6, "typed")


# --- GroupPage on its own -----------------------------------------------------------------------------------------


def test_group_page_embedded_without_the_dialog(qtbot: Any, cfg: Any) -> None:
    group_page = GroupPage("Editable")
    qtbot.addWidget(group_page)
    modified: list[bool] = []
    group_page.sig_modified.connect(modified.append)

    assert group_page.group().title == "Editable settings"
    assert group_page.values()["count"] == 3 and group_page.values()["folder"] == Path("c:/data")
    assert not group_page.is_modified()

    spin = group_page.editor_widget("count")
    assert isinstance(spin, QtWidgets.QSpinBox)
    spin.setValue(9)
    assert group_page.is_modified() and modified == [True]
    assert group_page.values()["count"] == 9 and cfg.count == 3

    group_page.revert()
    assert spin.value() == 3 and not group_page.is_modified() and modified == [True, False]

    spin.setValue(4)
    assert group_page.apply() is True
    assert cfg.count == 4 and not group_page.is_modified()

    with pytest.raises(KeyError):
        group_page.editor_widget("internal")
    with pytest.raises(KeyError):
        GroupPage("Nope")


def test_group_page_apply_refuses_invalid_values(qtbot: Any, cfg: Any) -> None:
    group_page = GroupPage(type(cfg))
    qtbot.addWidget(group_page)
    cast(QtWidgets.QSpinBox, group_page.editor_widget("count")).setValue(9)
    cast(QtWidgets.QSpinBox, group_page.editor_widget("limited")).setValue(50)

    assert group_page.validate() is False
    assert group_page.apply() is False
    assert (cfg.count, cfg.limited) == (3, 1)
    with pytest.raises(ValueError):
        group_page.values()


# --- hooks --------------------------------------------------------------------------------------------------------


class ColorButton(QtWidgets.QPushButton):
    """A widget without a USER property of its own that fits the value: QAbstractButton's is `checked`."""

    colorChanged = QtCore.Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._color = "#000000"

    def color(self) -> str:
        return self._color

    def setColor(self, color: str) -> None:
        if color != self._color:
            self._color = color
            self.colorChanged.emit(color)


def test_hooks_resolution(qtbot: Any) -> None:
    def read_write(widget: QtWidgets.QWidget, value: Any) -> Any:
        qtbot.addWidget(widget)
        hooks = hooks_for(widget)
        hooks.set_value(widget, value)
        return hooks.get_value(widget)

    assert read_write(QtWidgets.QSpinBox(), 5) == 5
    assert read_write(QtWidgets.QDoubleSpinBox(), "1.5") == 1.5
    assert read_write(QtWidgets.QLineEdit(), "text") == "text"
    assert read_write(QtWidgets.QPlainTextEdit(), "plain") == "plain"
    assert read_write(QtWidgets.QTextEdit(), "<b>not html</b>") == "<b>not html</b>"
    assert read_write(QtWidgets.QCheckBox(), True) is True
    assert read_write(AnimatedToggleSwitch(), True) is True
    assert read_write(QtWidgets.QSlider(), 7) == 7
    assert read_write(plain_combo(), 20) == 20
    assert read_write(shape_combo(), Shape.Square.value) is Shape.Square
    assert read_write(enum_combo(), "slow") == Method.Slow
    assert read_write(DecimalSpinBox(), "0.5") == decimal.Decimal("0.5")

    spin = QtWidgets.QSpinBox()
    qtbot.addWidget(spin)
    assert hooks_for(spin).value_changed(spin) == spin.valueChanged
    with pytest.raises(TypeError, match="QSpinBox.value does not accept 'abc'"):
        hooks_for(spin).set_value(spin, "abc")

    label = QtWidgets.QLabel()
    qtbot.addWidget(label)
    with pytest.raises(LookupError, match="QLabel"):
        hooks_for(label)


def test_subclass_user_property_beats_hooks_registered_for_a_base_class(qtbot: Any) -> None:
    combo = enum_combo()
    qtbot.addWidget(combo)
    hooks = hooks_for(combo)
    assert hooks.value_changed(combo) == combo.sig_current_enum_changed  # not QComboBox.currentIndexChanged

    fonts = QtWidgets.QFontComboBox()
    qtbot.addWidget(fonts)
    assert hooks_for(fonts).value_changed(fonts) == fonts.currentFontChanged


def test_resolving_hooks_keeps_static_meta_objects_valid(qtbot: Any, cfg: Any) -> None:
    # PySide invalidates Class.staticMetaObject when a widget whose metaObject() was called is destroyed.
    dlg = SettingsDialog()
    shiboken6.delete(dlg)
    for cls in (QtWidgets.QSpinBox, QtWidgets.QLineEdit, QtWidgets.QComboBox, EnumComboBox):
        assert shiboken6.isValid(cast(Any, cls).staticMetaObject), cls.__name__


def test_registered_and_explicit_hooks(qtbot: Any) -> None:
    color_hooks = EditorHooks.from_names("colorChanged", "color", "setColor")

    @config(group="Colors")
    class Colors:
        explicit: str = config_field(default="#111111", editor=ColorButton, hooks=color_hooks)
        registered: str = config_field(default="#222222", editor=ColorButton)

    colors = get_config(Colors)
    explicit_only = GroupPage(Colors)  # `registered` falls back to QAbstractButton's `checked` property
    qtbot.addWidget(explicit_only)
    assert cast(ColorButton, explicit_only.editor_widget("explicit")).color() == "#111111"

    qconfig.register_editor_hooks(ColorButton, color_hooks)
    try:
        group_page = GroupPage(Colors)
        qtbot.addWidget(group_page)
        button = cast(ColorButton, group_page.editor_widget("registered"))
        assert button.color() == "#222222"
        button.setColor("#abcdef")
        assert group_page.apply() and colors.registered == "#abcdef"
    finally:
        from pyside_config import _hooks

        del _hooks._registered[ColorButton]


def test_editor_factory_must_return_a_widget(qtbot: Any) -> None:
    @config(group="Broken")
    class Broken:
        flag: bool = config_field(default=False, editor=lambda: cast(Any, QtCore.QObject()))

    with pytest.raises(TypeError, match="returned QObject, not a QWidget"):
        GroupPage(Broken)


# --- deprecated ---------------------------------------------------------------------------------------------------


def test_create_editor_is_deprecated_and_behaves_as_before(qtbot: Any, cfg: Any) -> None:
    with pytest.warns(DeprecationWarning, match="SettingsDialog"):
        dlg = qconfig.create_editor(exclude=["Second"], window_title="Preferences")
    qtbot.addWidget(dlg)
    assert isinstance(dlg, SettingsDialog)
    assert dlg.isModal() and dlg.testAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
    assert dlg.windowTitle() == "Preferences" and tab_titles(dlg) == ["Editable settings"]
