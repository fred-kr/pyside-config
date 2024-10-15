import typing as t

from PySide6 import QtGui, QtWidgets

from .config import EditorWidgetInfo


def make_line_edit_info(
    label: str,
    widget_factory: t.Callable[..., QtWidgets.QLineEdit] = QtWidgets.QLineEdit,
    sig_value_changed: str = "textChanged",
    set_value_method: str = "setText",
    icon: QtGui.QIcon | None = None,
) -> EditorWidgetInfo[QtWidgets.QLineEdit]:
    return EditorWidgetInfo(
        label=label,
        widget_factory=widget_factory,
        sig_value_changed=sig_value_changed,
        set_value_method=set_value_method,
        icon=icon,
    )


def make_check_box_info(
    label: str,
    widget_factory: t.Callable[..., QtWidgets.QCheckBox] = QtWidgets.QCheckBox,
    sig_value_changed: str = "toggled",
    set_value_method: str = "setChecked",
    icon: QtGui.QIcon | None = None,
) -> EditorWidgetInfo[QtWidgets.QCheckBox]:
    return EditorWidgetInfo(
        label=label,
        widget_factory=widget_factory,
        sig_value_changed=sig_value_changed,
        set_value_method=set_value_method,
        icon=icon,
    )


def make_spin_box_info[T: QtWidgets.QSpinBox | QtWidgets.QDoubleSpinBox](
    label: str,
    widget_factory: t.Callable[..., T] = QtWidgets.QSpinBox,
    sig_value_changed: str = "valueChanged",
    set_value_method: str = "setValue",
    icon: QtGui.QIcon | None = None,
) -> EditorWidgetInfo[T]:
    return EditorWidgetInfo(
        label=label,
        widget_factory=widget_factory,
        sig_value_changed=sig_value_changed,
        set_value_method=set_value_method,
        icon=icon,
    )


def make_combo_box_info(
    label: str,
    widget_factory: t.Callable[..., QtWidgets.QComboBox] = QtWidgets.QComboBox,
    sig_value_changed: str = "currentIndexChanged",
    set_value_method: str = "setCurrentIndex",
    icon: QtGui.QIcon | None = None,
) -> EditorWidgetInfo[QtWidgets.QComboBox]:
    return EditorWidgetInfo(
        label=label,
        widget_factory=widget_factory,
        sig_value_changed=sig_value_changed,
        set_value_method=set_value_method,
        icon=icon,
    )
