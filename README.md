# pyside-config

Persistent application settings for PySide6. You declare each settings group as an `attrs` class; the package
stores the values in `QSettings`, coerces them back to the declared types on load, and generates a settings
dialog from the declarations. It is for PySide6 desktop applications that want typed settings without writing
`QSettings` key strings or dialog code by hand.

```python
from PySide6 import QtCore, QtWidgets
import pyside_config as qconfig
from pyside_config.helpers import make_spin_box_info

QtWidgets.QApplication.setOrganizationName("Acme")
QtWidgets.QApplication.setApplicationName("Viewer")


@qconfig.config(group_name="Plot")
class PlotConfig:
    click_radius: int = qconfig.config_field(
        default=20,
        editor=make_spin_box_info("Click radius", minimum=0, maximum=1000, suffix=" px"),
        description="Pixels around a click that are searched for a peak.",
    )


@qconfig.config(group_name="Internal", hidden=True)
class InternalConfig:
    window_geometry: QtCore.QByteArray = qconfig.config_field(factory=QtCore.QByteArray)


plot = qconfig.get_config(PlotConfig)
print(plot.click_radius)  # 20, or the stored value
plot.click_radius = 30  # coerced to int, written to QSettings, sig_value_changed emitted

app = QtWidgets.QApplication([])
qconfig.signals().sig_value_changed.connect(lambda group, name, value: print(group, name, value))
qconfig.create_editor().exec()  # one tab per visible group; OK applies, Cancel discards
qconfig.save()
```

Requires Python 3.14, PySide6 6.12 and [pyside-widgets](https://github.com/fred-kr/pyside-widgets) 0.4
(for `SettingCard`, `EnumComboBox` and `DecimalSpinBox`).

## Declare a group

`@config` makes the class an `attrs` class, creates one instance filled from `QSettings`, and registers it under
`group_name` (default: the class name). Fields are declared with `config_field`, which is `attrs.field` plus:

| Argument | Purpose |
|---|---|
| `editor` | An `EditorWidgetInfo`; fields without one are stored but not shown in the dialog. |
| `description` | Text under the editor in the dialog; also available through `iter_fields`. |
| `qtype` | Type to coerce stored values to when the annotation is not the right target. |

Plain `attrs.field(metadata={qconfig.EDITOR_KEY: ..., qconfig.DESCRIPTION_KEY: ...})` works as well.

`hidden=True` keeps a group out of the dialog. `register=False` declares a base class without an instance.

## Read and write values

`get_config(PlotConfig)` returns the typed instance; `get_config("Plot")` returns it by name. Reading an attribute
is a plain attribute read. Assigning one:

1. coerces the value to the declared type (skipped when the field has a `converter`),
2. runs the field's `converter` and `validator`,
3. writes it to `QSettings`,
4. emits `signals().sig_value_changed(group, name, value)` if the value differs from before.

Writes are flushed to permanent storage by `save()`, `reset()`, `restore_snapshot()`, the dialog's OK button, and
when the `QSettings` object is destroyed. Call `save()` when the main window closes.

## Types that round-trip

`QSettings` backends return `str` for most scalars (INI) or `"true"`/`"false"` for booleans (Windows registry),
and a one-element string list comes back as a `str`. `coerce` repairs: `bool`, `int`, `float`, `str`, `bytes`,
`decimal.Decimal`, `pathlib.Path`, `QByteArray`, `Enum` subclasses (by value, then by name), `X | None`,
`Literal`, `list[T]`, `tuple[T, ...]`, `set[T]` and `dict[K, V]`. Enums are stored by `.value`, `Decimal` and
`Path` as `str`. A stored value that cannot be coerced is replaced by the field default on load.

## The dialog

`create_editor(parent, exclude=(), window_title="Settings", include_hidden=False)` returns a modal `QDialog`
with one tab per group and one `SettingCard` per field with an editor. Edits are staged; OK applies them (one
`sig_value_changed` per changed field) and flushes the store, Cancel discards them. The card's reset button shows
the default in the editor and stages it like any other edit.

The dialog reads, writes and watches each widget through `EditorHooks`. Hooks are registered per widget class and
resolved through the MRO, so subclasses of `QAbstractButton`, `QAbstractSlider`, `QSpinBox`, `QDoubleSpinBox`,
`QComboBox`, `QLineEdit`, `QPlainTextEdit`, `QTextEdit`, `QKeySequenceEdit`, `QDateTimeEdit`, `QAction`, and
pyside-widgets' `EnumComboBox` and `DecimalSpinBox` need no configuration. For another widget either pass
`sig_value_changed`, `get_value_method` and `set_value_method` to `EditorWidgetInfo`, or call
`register_editor_hooks(WidgetClass, EditorHooks.from_names("valueChanged", "value", "setValue"))`.

The `make_*_info` helpers in `pyside_config.helpers` build an `EditorWidgetInfo` together with the widget's Qt
properties (`minimum`, `maximum`, `suffix`, ...), applied after the widget is created.

## Other functions

| Function | Effect |
|---|---|
| `save()` | Write all instances and flush. |
| `reset(exclude=())` | Restore defaults of all groups not excluded. |
| `clean(exclude=())` | Delete stored values (all, or all top-level groups not excluded). In-memory values are unchanged. |
| `update_value(group, key, value)` | Set one attribute by name. |
| `create_snapshot()` / `restore_snapshot(snapshot)` | Capture and restore all values as `{group: {field: value}}`. |
| `iter_fields(include_hidden=True)` | Yield `FieldInfo(group, name, type, default, label, description, hidden)` for documentation. |
| `groups()` | Registered instances by name. |
| `unregister(name)` | Remove a group from the registry. |
| `configure(settings_factory)` | Replace `QSettings()` with your own factory; call before the first `@config`. |
| `settings()` | The `QSettings` object in use. |

## Testing an application that uses pyside-config

Call `configure` before importing the module that declares the groups:

```python
pyside_config.configure(lambda: QtCore.QSettings(str(tmp_path / "s.ini"), QtCore.QSettings.Format.IniFormat))
```

No organization or application name is needed then, and the user's stored settings are never read or written.

## Development

```
uv sync
uv run pytest
uv run ruff check . && uv run pyright
```
