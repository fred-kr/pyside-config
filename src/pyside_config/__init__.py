import typing as t

import attrs
from PySide6 import QtWidgets

from .base import ConfigBase, WidgetPropertiesBase

__all__ = ["ConfigBase", "WidgetPropertiesBase", "EditorWidgetInfo"]


@attrs.define
class EditorWidgetInfo[W: QtWidgets.QWidget]:
    label: str
    widget_factory: t.Callable[..., W]
    sig_value_changed: str
    set_value_method: str
    widget_properties: WidgetPropertiesBase[W] | None = None
