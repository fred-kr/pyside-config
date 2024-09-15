import typing as t

import attrs
from PySide6 import QtWidgets

W = t.TypeVar("W", bound=QtWidgets.QWidget)


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
class WidgetPropertiesBase[W]:
    def apply_to_widget(self, widget: W) -> None:
        for field in attrs.fields(self.__class__):
            setter_name = field.metadata["setter"]
            prop_value = getattr(self, field.name)
            if setter_name and hasattr(widget, setter_name):
                getattr(widget, setter_name)(prop_value)


class EditorWidgetInfo[W](t.TypedDict):
    label: str
    widget_factory: t.Callable[..., W]
    widget_properties: t.NotRequired[WidgetPropertiesBase[W] | None]


@attrs.define
class SpinBoxProperties(WidgetPropertiesBase[QtWidgets.QSpinBox]):
    minimum: int = attrs.field(
        default=0, converter=int, validator=_check_lower_bound, metadata={"setter": "setMinimum"}
    )
    maximum: int = attrs.field(
        default=1_000_000, converter=int, validator=_check_upper_bound, metadata={"setter": "setMaximum"}
    )
    singleStep: int = attrs.field(
        default=1, converter=int, validator=_check_step_size, metadata={"setter": "setSingleStep"}
    )
    prefix: str = attrs.field(default="", converter=str, metadata={"setter": "setPrefix"})
    suffix: str = attrs.field(default="", converter=str, metadata={"setter": "setSuffix"})
    frame: bool = attrs.field(default=False, converter=bool, metadata={"setter": "setFrame"})


@attrs.define
class DoubleSpinBoxProperties(WidgetPropertiesBase[QtWidgets.QDoubleSpinBox]):
    minimum: float = attrs.field(
        default=0.0, converter=float, validator=_check_lower_bound, metadata={"setter": "setMinimum"}
    )
    maximum: float = attrs.field(
        default=1e6, converter=float, validator=_check_upper_bound, metadata={"setter": "setMaximum"}
    )
    singleStep: float = attrs.field(
        default=0.1, converter=float, validator=_check_step_size, metadata={"setter": "setSingleStep"}
    )
    decimals: int = attrs.field(
        default=2, converter=int, validator=attrs.validators.ge(0), metadata={"setter": "setDecimals"}
    )
    prefix: str = attrs.field(default="", converter=str, metadata={"setter": "setPrefix"})
    suffix: str = attrs.field(default="", converter=str, metadata={"setter": "setSuffix"})


@attrs.define
class LineEditProperties(WidgetPropertiesBase[QtWidgets.QLineEdit]):
    frame: bool = attrs.field(default=False, converter=bool, metadata={"setter": "setFrame"})
