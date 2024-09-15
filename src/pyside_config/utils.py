import inspect
import sys
import typing as t

import attrs
from PySide6 import QtCore, QtWidgets

from .widgets import EnumComboBox


def get_setting_path(inst_or_cls: attrs.AttrsInstance | t.Type[attrs.AttrsInstance], attr: t.Any) -> str:
    class_name = inst_or_cls.__name__ if inspect.isclass(inst_or_cls) else inst_or_cls.__class__.__name__
    return f"{class_name}/{attr.name}"


def sync[T](inst: attrs.AttrsInstance, attr: t.Any, value: T) -> T:
    path = get_setting_path(inst, attr)
    settings = QtCore.QSettings()
    if path and path in settings.allKeys():
        settings.setValue(path, value)
        settings.sync()
    return value


def get_app_dir():
    app_instance = QtWidgets.QApplication.instance()
    return (
        QtCore.QDir(app_instance.applicationDirPath()).canonicalPath()
        if hasattr(sys, "frozen") and app_instance is not None
        else QtCore.QDir.current().canonicalPath()
    )


def create_editor_widget(attrs_inst: attrs.AttrsInstance) -> QtWidgets.QWidget:
    container = QtWidgets.QWidget()
    layout = QtWidgets.QFormLayout(container)

    for field in attrs.fields(attrs_inst.__class__):
        editor_info = field.metadata.get("editor", None)
        if not editor_info:
            continue

        # Use a factory function or a widget class directly
        widget = editor_info["widget_factory"]()
        widget_properties = editor_info.get("widget_properties")

        value = getattr(attrs_inst, field.name)

        # Set widget properties based on field type
        if isinstance(widget, (QtWidgets.QSpinBox, QtWidgets.QDoubleSpinBox)):
            widget.setValue(value)
            widget.valueChanged.connect(lambda val, f=field: setattr(attrs_inst, f.name, val))
        elif isinstance(widget, QtWidgets.QLineEdit):
            widget.setText(value)
            widget.textChanged.connect(lambda text, f=field: setattr(attrs_inst, f.name, text))
        elif isinstance(widget, EnumComboBox):
            widget.set_enum_class(field.type)
            widget.set_current_enum(value)
            widget.sig_current_enum_changed.connect(lambda val, f=field: setattr(attrs_inst, f.name, val))

        if widget_properties is not None:
            widget_properties.apply_to_widget(widget)

        layout.addRow(editor_info.get("label"), widget)

    return container
