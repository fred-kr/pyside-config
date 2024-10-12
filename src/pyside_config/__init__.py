import functools
import typing as t

import attrs
from PySide6 import QtGui, QtWidgets

from ._base import ConfigBase, WidgetPropertiesBase, update_qsettings

__all__ = ["ConfigBase", "WidgetPropertiesBase", "EditorWidgetInfo", "define_config"]


@attrs.define
class EditorWidgetInfo[W: QtWidgets.QWidget]:
    label: str
    widget_factory: t.Callable[..., W]
    sig_value_changed: str
    set_value_method: str
    icon: QtGui.QIcon | None = None
    widget_properties: WidgetPropertiesBase[W] | None = None


define_config = functools.partial(attrs.define, on_setattr=update_qsettings)
