import typing as t

import attrs
from attr._make import Factory
from PySide6 import QtCore, QtWidgets

from .utils import create_editor_widget, get_setting_path


@attrs.define
class ConfigBase:
    def to_dict(self) -> dict[str, t.Any]:
        return attrs.asdict(self)

    @classmethod
    def from_qsettings(cls) -> "ConfigBase":
        settings = QtCore.QSettings()
        init_values = {}
        for field in attrs.fields(cls):
            path = get_setting_path(cls, field)
            value = settings.value(path, field.default)
            if isinstance(value, Factory):
                value = value.factory()
            init_values[field.name] = value

        return cls(**init_values)

    def to_qsettings(self) -> None:
        settings = QtCore.QSettings()
        for field in attrs.fields(self.__class__):
            path = get_setting_path(self, field)
            value = getattr(self, field.name)
            settings.setValue(path, value)

        settings.sync()

    def restore_defaults(self) -> None:
        for field in attrs.fields(self.__class__):
            setattr(self, field.name, field.default)

        self.to_qsettings()

    def create_editor(self) -> QtWidgets.QWidget:
        return create_editor_widget(self)
