import decimal
import typing as t

from PySide6 import QtGui, QtWidgets

from .config import EditorWidgetInfo
from .properties import (
    CheckBoxProperties,
    ComboBoxProperties,
    DoubleSpinBoxProperties,
    LineEditProperties,
    SpinBoxProperties,
)


class LineEditKwargs(t.TypedDict, total=False):
    clearButtonEnabled: bool
    completer: QtWidgets.QCompleter | None
    hasFrame: bool


class CheckBoxKwargs(t.TypedDict, total=False):
    isTristate: bool


class SpinBoxKwargs(t.TypedDict, total=False):
    minimum: int
    maximum: int
    singleStep: int
    prefix: str
    suffix: str
    hasFrame: bool


class DoubleSpinBoxKwargs(t.TypedDict, total=False):
    minimum: float
    maximum: float
    singleStep: float
    prefix: str
    suffix: str
    hasFrame: bool


class DecimalSpinBoxKwargs(t.TypedDict, total=False):
    minimum: decimal.Decimal
    maximum: decimal.Decimal
    singleStep: decimal.Decimal
    prefix: str
    suffix: str
    hasFrame: bool


class ComboBoxKwargs(t.TypedDict, total=False):
    isEditable: bool
    hasFrame: bool


def make_line_edit_info(
    label: str,
    widget_factory: t.Callable[..., QtWidgets.QLineEdit] = QtWidgets.QLineEdit,
    sig_value_changed: str = "textChanged",
    set_value_method: str = "setText",
    icon: QtGui.QIcon | None = None,
    **kwargs: t.Unpack[LineEditKwargs],
) -> EditorWidgetInfo[QtWidgets.QLineEdit]:
    return EditorWidgetInfo(
        label=label,
        widget_factory=widget_factory,
        sig_value_changed=sig_value_changed,
        set_value_method=set_value_method,
        icon=icon,
        widget_properties=LineEditProperties(**kwargs),
    )


def make_check_box_info(
    label: str,
    widget_factory: t.Callable[..., QtWidgets.QCheckBox] = QtWidgets.QCheckBox,
    sig_value_changed: str = "toggled",
    set_value_method: str = "setChecked",
    icon: QtGui.QIcon | None = None,
    **kwargs: t.Unpack[CheckBoxKwargs],
) -> EditorWidgetInfo[QtWidgets.QCheckBox]:
    return EditorWidgetInfo(
        label=label,
        widget_factory=widget_factory,
        sig_value_changed=sig_value_changed,
        set_value_method=set_value_method,
        icon=icon,
        widget_properties=CheckBoxProperties(**kwargs),
    )


def make_spin_box_info(
    label: str,
    widget_factory: t.Callable[..., QtWidgets.QSpinBox] = QtWidgets.QSpinBox,
    sig_value_changed: str = "valueChanged",
    set_value_method: str = "setValue",
    icon: QtGui.QIcon | None = None,
    **kwargs: t.Unpack[SpinBoxKwargs],
) -> EditorWidgetInfo[QtWidgets.QSpinBox]:
    return EditorWidgetInfo(
        label=label,
        widget_factory=widget_factory,
        sig_value_changed=sig_value_changed,
        set_value_method=set_value_method,
        icon=icon,
        widget_properties=SpinBoxProperties(**kwargs),
    )


def make_double_spin_box_info(
    label: str,
    widget_factory: t.Callable[..., QtWidgets.QDoubleSpinBox] = QtWidgets.QDoubleSpinBox,
    sig_value_changed: str = "valueChanged",
    set_value_method: str = "setValue",
    icon: QtGui.QIcon | None = None,
    **kwargs: t.Unpack[DoubleSpinBoxKwargs],
) -> EditorWidgetInfo[QtWidgets.QDoubleSpinBox]:
    return EditorWidgetInfo(
        label=label,
        widget_factory=widget_factory,
        sig_value_changed=sig_value_changed,
        set_value_method=set_value_method,
        icon=icon,
        widget_properties=DoubleSpinBoxProperties(**kwargs),
    )


def make_decimal_spin_box_info(
    label: str,
    widget_factory: t.Callable[..., QtWidgets.QDoubleSpinBox] = QtWidgets.QDoubleSpinBox,
    sig_value_changed: str = "valueChanged",
    set_value_method: str = "setValue",
    icon: QtGui.QIcon | None = None,
    **kwargs: t.Unpack[DecimalSpinBoxKwargs],
) -> EditorWidgetInfo[QtWidgets.QDoubleSpinBox]:
    return EditorWidgetInfo(
        label=label,
        widget_factory=widget_factory,
        sig_value_changed=sig_value_changed,
        set_value_method=set_value_method,
        icon=icon,
        widget_properties=DoubleSpinBoxProperties(**kwargs),
    )


def make_combo_box_info(
    label: str,
    widget_factory: t.Callable[..., QtWidgets.QComboBox] = QtWidgets.QComboBox,
    sig_value_changed: str = "currentIndexChanged",
    set_value_method: str = "setCurrentIndex",
    icon: QtGui.QIcon | None = None,
    **kwargs: t.Unpack[ComboBoxKwargs],
) -> EditorWidgetInfo[QtWidgets.QComboBox]:
    return EditorWidgetInfo(
        label=label,
        widget_factory=widget_factory,
        sig_value_changed=sig_value_changed,
        set_value_method=set_value_method,
        icon=icon,
        widget_properties=ComboBoxProperties(**kwargs),
    )
