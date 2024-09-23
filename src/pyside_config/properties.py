import typing as t

import attrs
from PySide6 import QtWidgets

from .base import SETTER_METADATA_KEY, WidgetPropertiesBase

__all__ = ["SpinBoxProperties", "DoubleSpinBoxProperties", "LineEditProperties"]


def _check_step_size(inst: "SpinBoxProperties | DoubleSpinBoxProperties", attr: t.Any, value: int | float) -> None:
    max_step = inst.maximum - inst.minimum
    if value <= 0 or value > max_step:
        raise ValueError(f"Step must be higher than 0 and less than {max_step}.")


def _check_upper_bound(inst: "SpinBoxProperties | DoubleSpinBoxProperties", attr: t.Any, value: int | float) -> None:
    if value <= inst.minimum:
        raise ValueError("Max must be greater than min.")


def _check_lower_bound(inst: "SpinBoxProperties | DoubleSpinBoxProperties", attr: t.Any, value: int | float) -> None:
    if value >= inst.maximum:
        raise ValueError("Min must be less than max.")


@attrs.define
class SpinBoxProperties(WidgetPropertiesBase[QtWidgets.QSpinBox]):
    minimum: int = attrs.field(
        default=0, converter=int, validator=_check_lower_bound, metadata={SETTER_METADATA_KEY: "setMinimum"}
    )
    maximum: int = attrs.field(
        default=1_000_000, converter=int, validator=_check_upper_bound, metadata={SETTER_METADATA_KEY: "setMaximum"}
    )
    singleStep: int = attrs.field(
        default=1, converter=int, validator=_check_step_size, metadata={SETTER_METADATA_KEY: "setSingleStep"}
    )
    prefix: str | None = attrs.field(default=None, metadata={SETTER_METADATA_KEY: "setPrefix"})
    suffix: str | None = attrs.field(default=None, metadata={SETTER_METADATA_KEY: "setSuffix"})
    hasFrame: bool = attrs.field(default=False, converter=bool, metadata={SETTER_METADATA_KEY: "setFrame"})


@attrs.define
class DoubleSpinBoxProperties(WidgetPropertiesBase[QtWidgets.QDoubleSpinBox]):
    minimum: float = attrs.field(
        default=0.0, converter=float, validator=_check_lower_bound, metadata={SETTER_METADATA_KEY: "setMinimum"}
    )
    maximum: float = attrs.field(
        default=1e6, converter=float, validator=_check_upper_bound, metadata={SETTER_METADATA_KEY: "setMaximum"}
    )
    singleStep: float = attrs.field(
        default=0.1, converter=float, validator=_check_step_size, metadata={SETTER_METADATA_KEY: "setSingleStep"}
    )
    decimals: int = attrs.field(
        default=2, converter=int, validator=attrs.validators.ge(0), metadata={SETTER_METADATA_KEY: "setDecimals"}
    )
    prefix: str | None = attrs.field(default=None, metadata={SETTER_METADATA_KEY: "setPrefix"})
    suffix: str | None = attrs.field(default=None, metadata={SETTER_METADATA_KEY: "setSuffix"})
    hasFrame: bool = attrs.field(default=False, converter=bool, metadata={SETTER_METADATA_KEY: "setFrame"})


@attrs.define
class LineEditProperties(WidgetPropertiesBase[QtWidgets.QLineEdit]):
    clearButtonEnabled: bool = attrs.field(
        default=True, converter=bool, metadata={SETTER_METADATA_KEY: "setClearButtonEnabled"}
    )
    completer: QtWidgets.QCompleter | None = attrs.field(default=None, metadata={SETTER_METADATA_KEY: "setCompleter"})
    hasFrame: bool = attrs.field(default=False, converter=bool, metadata={SETTER_METADATA_KEY: "setFrame"})


@attrs.define
class ComboBoxProperties(WidgetPropertiesBase[QtWidgets.QComboBox]):
    isEditable: bool = attrs.field(default=False, converter=bool, metadata={SETTER_METADATA_KEY: "setEditable"})
    hasFrame: bool = attrs.field(default=False, converter=bool, metadata={SETTER_METADATA_KEY: "setFrame"})
