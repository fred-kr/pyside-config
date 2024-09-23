import typing as t

import attrs
from PySide6 import QtWidgets

from .base import ConfigBase, WidgetPropertiesBase, update_qsettings

__all__ = ["ConfigBase", "WidgetPropertiesBase", "EditorWidgetInfo"]


@attrs.define
class EditorWidgetInfo[W: QtWidgets.QWidget]:
    label: str
    widget_factory: t.Callable[..., W]
    sig_value_changed: str
    set_value_method: str
    widget_properties: WidgetPropertiesBase[W] | None = None


@t.dataclass_transform(field_specifiers=(attrs.field,))
def config(cls: type) -> type:
    return attrs.define(cls, on_setattr=update_qsettings)
