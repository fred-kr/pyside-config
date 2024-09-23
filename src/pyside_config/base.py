import inspect
import typing as t

import attrs
from attr._make import Factory
from PySide6 import QtCore, QtGui, QtWidgets

SETTER_METADATA_KEY = "__setter"


def get_setting_path(inst_or_cls: attrs.AttrsInstance | t.Type[attrs.AttrsInstance], attr: t.Any) -> str:
    class_name = inst_or_cls.__name__ if inspect.isclass(inst_or_cls) else inst_or_cls.__class__.__name__
    return f"{class_name}/{attr.name}"


def update_qsettings[T](inst: attrs.AttrsInstance, attr: t.Any, value: T) -> T:
    path = get_setting_path(inst, attr)
    settings = QtCore.QSettings()
    if path:
        if isinstance(value, QtGui.QColor):
            settings.setValue(path, value.name())
        else:
            settings.setValue(path, value)
        settings.sync()
    return value


@attrs.define
class ConfigBase:
    @classmethod
    def from_qsettings(cls) -> t.Self:
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

    def create_editor(self, **kwargs: t.Any) -> QtWidgets.QWidget:
        """
        Creates a widget containing a form layout with editors for each field in the config class.

        Args:
            **kwargs: Additional keyword arguments to pass to the widget factory.

        Returns:
            QtWidgets.QWidget: The created widget.
        """
        container_widget = QtWidgets.QWidget()

        layout = QtWidgets.QFormLayout(container_widget)

        for field in attrs.fields(self.__class__):
            editor_info = field.metadata.get("editor", None)
            if not editor_info:
                continue

            widget = editor_info.widget_factory(**kwargs)
            widget_properties = editor_info.widget_properties

            value = getattr(self, field.name)

            # Set the initial value of the editor
            getattr(widget, editor_info.set_value_method)(value)

            # Update the config value whenever the editor's valueChanged (varies depending on the widget type) signal is emitted
            getattr(widget, editor_info.sig_value_changed).connect(lambda val, f=field: setattr(self, f.name, val))

            if widget_properties is not None:
                widget_properties.apply_to_widget(widget)

            layout.addRow(editor_info.label, widget)

        return container_widget


@attrs.define
class WidgetPropertiesBase[W: QtWidgets.QWidget]:
    styleSheet: str | None = attrs.field(default=None, metadata={SETTER_METADATA_KEY: "setStyleSheet"})

    def apply_to_widget(self, widget: W) -> None:
        for field in attrs.fields(self.__class__):
            property_value = getattr(self, field.name)
            getattr(widget, field.metadata[SETTER_METADATA_KEY])(property_value)
