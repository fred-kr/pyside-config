import typing as t

import attrs
from PySide6 import QtWidgets

SETTER_KEY = "__setter"


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
class WidgetPropertiesBase[W: QtWidgets.QWidget]:
    """
    Base class for widget properties.
    """

    styleSheet: str | None = attrs.field(default="", metadata={SETTER_KEY: "setStyleSheet"})

    def apply_to_widget(self, widget: W) -> None:
        """
        Applies the current values of the class attributes to the specified widget.

        This method iterates through the fields of the class and sets the corresponding properties on the provided
        widget, using defined setter methods.

        Args:
            widget (W): The widget to which the attribute values will be applied.
        """
        for field in attrs.fields(self.__class__):
            property_value = getattr(self, field.name)
            if field.name == "styleSheet" and property_value == "":  # allow using None to clear a style sheet
                continue
            getattr(widget, field.metadata[SETTER_KEY])(property_value)


@attrs.define
class SpinBoxProperties(WidgetPropertiesBase[QtWidgets.QSpinBox]):
    minimum: int = attrs.field(
        default=0, converter=int, validator=_check_lower_bound, metadata={SETTER_KEY: "setMinimum"}
    )
    maximum: int = attrs.field(
        default=1_000_000, converter=int, validator=_check_upper_bound, metadata={SETTER_KEY: "setMaximum"}
    )
    singleStep: int = attrs.field(
        default=1, converter=int, validator=_check_step_size, metadata={SETTER_KEY: "setSingleStep"}
    )
    prefix: str | None = attrs.field(default=None, metadata={SETTER_KEY: "setPrefix"})
    suffix: str | None = attrs.field(default=None, metadata={SETTER_KEY: "setSuffix"})
    hasFrame: bool = attrs.field(default=False, metadata={SETTER_KEY: "setFrame"})


@attrs.define
class DoubleSpinBoxProperties(WidgetPropertiesBase[QtWidgets.QDoubleSpinBox]):
    minimum: float = attrs.field(
        default=0.0, converter=float, validator=_check_lower_bound, metadata={SETTER_KEY: "setMinimum"}
    )
    maximum: float = attrs.field(
        default=1e6, converter=float, validator=_check_upper_bound, metadata={SETTER_KEY: "setMaximum"}
    )
    singleStep: float = attrs.field(
        default=0.1, converter=float, validator=_check_step_size, metadata={SETTER_KEY: "setSingleStep"}
    )
    decimals: int = attrs.field(
        default=2, converter=int, validator=attrs.validators.ge(0), metadata={SETTER_KEY: "setDecimals"}
    )
    prefix: str | None = attrs.field(default=None, metadata={SETTER_KEY: "setPrefix"})
    suffix: str | None = attrs.field(default=None, metadata={SETTER_KEY: "setSuffix"})
    hasFrame: bool = attrs.field(default=False, metadata={SETTER_KEY: "setFrame"})


@attrs.define
class LineEditProperties(WidgetPropertiesBase[QtWidgets.QLineEdit]):
    clearButtonEnabled: bool = attrs.field(default=True, converter=bool, metadata={SETTER_KEY: "setClearButtonEnabled"})
    completer: QtWidgets.QCompleter | None = attrs.field(default=None, metadata={SETTER_KEY: "setCompleter"})
    hasFrame: bool = attrs.field(default=False, metadata={SETTER_KEY: "setFrame"})


@attrs.define
class ComboBoxProperties(WidgetPropertiesBase[QtWidgets.QComboBox]):
    isEditable: bool = attrs.field(default=False, metadata={SETTER_KEY: "setEditable"})
    hasFrame: bool = attrs.field(default=False, metadata={SETTER_KEY: "setFrame"})
