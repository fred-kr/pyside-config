"""
Widget properties applied to an editor after it is created.

Each class lists Qt properties as `attrs` fields whose metadata names the setter. `apply_to_widget` calls each
setter with the field's value. Use the `make_*_info` helpers in `pyside_config.helpers` instead of constructing
these directly.
"""

import decimal

import attrs
from PySide6 import QtGui, QtWidgets

SETTER_KEY = "__setter"
"""Field metadata key naming the widget method that applies the property."""


@attrs.define
class WidgetPropertiesBase[W: QtWidgets.QWidget | QtGui.QAction]:
    """Base class: a style sheet, applied only when not empty."""

    styleSheet: str | None = attrs.field(default="", metadata={SETTER_KEY: "setStyleSheet"})

    def apply_to_widget(self, widget: W) -> None:
        """Calls each field's setter on `widget` with the field's value."""
        for field in attrs.fields(type(self)):
            value = getattr(self, field.name)
            if field.name == "styleSheet" and value == "":  # `None` clears the style sheet, "" leaves it alone
                continue
            getattr(widget, field.metadata[SETTER_KEY])(value)


type SpinBoxNumber = int | float | decimal.Decimal


@attrs.define
class SpinBoxProperties(WidgetPropertiesBase[QtWidgets.QAbstractSpinBox]):
    minimum: SpinBoxNumber = attrs.field(default=0, metadata={SETTER_KEY: "setMinimum"})
    maximum: SpinBoxNumber = attrs.field(default=1_000_000, metadata={SETTER_KEY: "setMaximum"})
    singleStep: SpinBoxNumber = attrs.field(default=1, metadata={SETTER_KEY: "setSingleStep"})
    prefix: str = attrs.field(default="", metadata={SETTER_KEY: "setPrefix"})
    suffix: str = attrs.field(default="", metadata={SETTER_KEY: "setSuffix"})
    hasFrame: bool = attrs.field(default=False, metadata={SETTER_KEY: "setFrame"})


@attrs.define
class DecimalSpinBoxProperties(SpinBoxProperties):
    """Properties of a `DecimalSpinBox` or `QDoubleSpinBox`."""

    decimals: int = attrs.field(default=2, metadata={SETTER_KEY: "setDecimals"})


DoubleSpinBoxProperties = DecimalSpinBoxProperties
"""Properties of a `QDoubleSpinBox`; the same setters as `DecimalSpinBoxProperties`."""


@attrs.define
class LineEditProperties(WidgetPropertiesBase[QtWidgets.QLineEdit]):
    clearButtonEnabled: bool = attrs.field(default=True, converter=bool, metadata={SETTER_KEY: "setClearButtonEnabled"})
    completer: QtWidgets.QCompleter | None = attrs.field(default=None, metadata={SETTER_KEY: "setCompleter"})
    hasFrame: bool = attrs.field(default=False, metadata={SETTER_KEY: "setFrame"})


@attrs.define
class ComboBoxProperties(WidgetPropertiesBase[QtWidgets.QComboBox]):
    isEditable: bool = attrs.field(default=False, metadata={SETTER_KEY: "setEditable"})
    hasFrame: bool = attrs.field(default=False, metadata={SETTER_KEY: "setFrame"})


@attrs.define
class CheckBoxProperties(WidgetPropertiesBase[QtWidgets.QCheckBox]):
    isTristate: bool = attrs.field(default=False, metadata={SETTER_KEY: "setTristate"})
