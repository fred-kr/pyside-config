import functools
import typing as t

import attrs
from PySide6 import QtWidgets

from .base import ConfigBase, WidgetPropertiesBase, update_qsettings

__all__ = ["ConfigBase", "WidgetPropertiesBase", "EditorWidgetInfo", "config"]


@attrs.define
class EditorWidgetInfo[W: QtWidgets.QWidget]:
    label: str
    widget_factory: t.Callable[..., W]
    sig_value_changed: str
    set_value_method: str
    widget_properties: WidgetPropertiesBase[W] | None = None


config = functools.partial(attrs.define, on_setattr=update_qsettings)


class ConfigManager:

    _instance: "ConfigManager | None" = None

    config_registry: dict[str, t.Type[ConfigBase]] = {}

    def __new__(cls) -> "ConfigManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)

        return cls._instance

    @classmethod
    def register_config(cls, config_class: t.Type[ConfigBase]) -> t.Type[ConfigBase]:
        cls.config_registry[config_class.__name__] = config_class
        return config_class