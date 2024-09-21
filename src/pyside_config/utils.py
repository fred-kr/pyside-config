import inspect
import sys
import typing as t

import attrs
from PySide6 import QtCore, QtWidgets

from .properties import EditorWidgetInfo


def get_setting_path(inst_or_cls: attrs.AttrsInstance | t.Type[attrs.AttrsInstance], attr: t.Any) -> str:
    class_name = inst_or_cls.__name__ if inspect.isclass(inst_or_cls) else inst_or_cls.__class__.__name__
    return f"{class_name}/{attr.name}"


def sync[T](inst: attrs.AttrsInstance, attr: t.Any, value: T) -> T:
    path = get_setting_path(inst, attr)
    settings = QtCore.QSettings()
    if path:
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
        editor_info: EditorWidgetInfo[QtWidgets.QWidget] | None = field.metadata.get("editor", None)
        if not editor_info:
            continue

        # Use a factory function or a widget class directly
        widget = editor_info["widget_factory"]()
        change_signal_name = editor_info["change_signal_name"]
        widget_properties = editor_info.get("widget_properties")

        value = getattr(attrs_inst, field.name)

        set_value_name = editor_info["set_value_name"]

        getattr(widget, set_value_name)(value)
        getattr(widget, change_signal_name).connect(lambda val, f=field: setattr(attrs_inst, f.name, val))

        # # Set widget properties based on field type
        # if isinstance(widget, (QtWidgets.QSpinBox, QtWidgets.QDoubleSpinBox)):
        #     widget.setValue(value)
        #     getattr(widget, change_signal_name).connect(lambda val, f=field: setattr(attrs_inst, f.name, val))
        #     # widget.valueChanged.connect(lambda val, f=field: setattr(attrs_inst, f.name, val))
        # elif isinstance(widget, QtWidgets.QLineEdit):
        #     widget.setText(value)
        #     widget.textChanged.connect(lambda text, f=field: setattr(attrs_inst, f.name, text))
        # elif isinstance(widget, EnumComboBox):
        #     widget.set_enum_class(field.type)
        #     widget.set_current_enum(value)
        #     widget.sig_current_enum_changed.connect(lambda val, f=field: setattr(attrs_inst, f.name, val))
        # elif isinstance(widget, QtWidgets.QCheckBox):
        #     widget.setChecked(value)
        #     widget.checkStateChanged.connect(lambda check_state, f=field: setattr(attrs_inst, f.name, check_state == QtCore.Qt.CheckState.Checked))

        if widget_properties is not None:
            widget_properties.apply_to_widget(widget)

        layout.addRow(editor_info.get("label"), widget)

    return container
