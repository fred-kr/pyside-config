# pyside-config

Persistent application settings for PySide6. You declare each settings group as a class with typed fields. The
package stores the values in `QSettings`, converts them back to the declared types on load, and builds a settings
dialog from the declarations. It is for PySide6 desktop applications that want typed settings without writing
`QSettings` key strings or dialog code by hand.

```python
import sys

from PySide6 import QtWidgets

import pyside_config as qconfig


@qconfig.config(group="Plot")
class PlotConfig:
    click_radius: int = qconfig.config_field(
        default=20,
        description="Pixels around a click that are searched for a peak.",
        editor=lambda: QtWidgets.QSpinBox(minimum=0, maximum=1000, suffix=" px"),
    )
    show_grid: bool = qconfig.config_field(default=True, editor=QtWidgets.QCheckBox)
    last_folder: str = qconfig.config_field(default="")  # stored, but not shown in the dialog


app = QtWidgets.QApplication(sys.argv)
app.setOrganizationName("Acme")
app.setApplicationName("Viewer")

plot = qconfig.get_config(PlotConfig)
qconfig.signals().sig_value_changed.connect(lambda group, name, value: print("changed:", group, name, value))

print(plot.click_radius)
plot.click_radius = 30  # validated, written to QSettings, announced on the signal
print(plot.click_radius + 1)

dialog = qconfig.SettingsDialog()
dialog.show()
app.exec()
qconfig.sync()
```

Output of the first run, if you close the dialog without changing anything:

```text
20
changed: Plot click_radius 30
31
```

The second run prints `30` first, because the value was stored.

## Install

Requires Python 3.14 or later, PySide6 6.12 and [pyside-widgets](https://github.com/fred-kr/pyside-widgets) 0.5, which
provides the `SettingCard` the dialog is built from. Neither package is on PyPI. Install both from GitHub:

```console
uv add "pyside-config @ git+https://github.com/fred-kr/pyside-config" "pyside-widgets @ git+https://github.com/fred-kr/pyside-widgets"
```

## Declare a group

`@config` turns the class into an [attrs](https://www.attrs.org) class and registers it as a settings group.
Declaring a group reads nothing. The first `get_config` call for the group creates its single instance and fills it
from `QSettings`.

| `@config` argument | Default | Purpose |
|---|---|---|
| `group` | the class name | The `QSettings` group the fields are stored under. Changing it orphans stored values. |
| `title` | `group` | The tab title in the dialog. Safe to change at any time. |
| `hidden` | `False` | Leave the group out of the dialog. |
| `register` | `True` | `False` declares a base class that only contributes fields to subclasses. |

Every field is declared with `config_field`, which is `attrs.field` plus the arguments below. A field needs
`default` or `factory`; a class with a field that has neither raises `TypeError` at declaration.

| `config_field` argument | Default | Purpose |
|---|---|---|
| `default` | required unless `factory` is given | The value used when nothing is stored. |
| `factory` | `None` | Zero-argument callable producing the default. Use it for mutable defaults such as `list`. |
| `editor` | `None` | Zero-argument callable returning the editor widget. Without it the field is stored but not shown. |
| `label` | the field name, underscores as spaces | Title of the field in the dialog. |
| `description` | `""` | Text under the label. Also available through `iter_fields`. |
| `icon` | `None` | `QIcon` shown left of the label. |
| `hooks` | `None` | `EditorHooks` for a widget the package cannot read by itself. See [Editor widgets](#editor-widgets). |
| `qtype` | the annotation | Type that stored values are converted to, when the annotation is not the right target. |
| `validator`, `converter`, ... | | Passed to `attrs.field`. |

Set the widget's Qt properties in the constructor call of `editor`. PySide6 accepts every Qt property as a keyword
argument, so no helper is needed.

A hidden group holds state that the application remembers but the user does not edit:

```python
from PySide6 import QtCore


@qconfig.config(group="Internal", hidden=True)
class InternalConfig:
    window_geometry: QtCore.QByteArray = qconfig.config_field(factory=QtCore.QByteArray)
    recent_files: list[str] = qconfig.config_field(factory=list)
```

## Read and write values

`get_config(PlotConfig)` returns the instance with its declared type, so a type checker knows that
`plot.click_radius` is an `int`. `get_config("Plot")` returns the same instance by group name.

Reading an attribute is a plain attribute read. Assigning one does four things, in this order:

1. It converts the value to the declared type. A field with a `converter` skips this step.
2. It runs the field's `converter` and `validator`. If either raises, nothing changes.
3. It stores the value on the instance and writes it to `QSettings`.
4. It emits `signals().sig_value_changed(group, name, value)` if the value differs from the previous one. A slot
   that reads the instance sees the new value.

```python
import attrs


@qconfig.config(group="Export", title="Export options")
class ExportConfig:
    decimals: int = qconfig.config_field(
        default=3,
        editor=lambda: QtWidgets.QSpinBox(maximum=20),
        validator=attrs.validators.le(10),
    )


export = qconfig.get_config(ExportConfig)
try:
    export.decimals = 11
except ValueError as error:
    print(error)
print(export.decimals)
```

```text
'decimals' must be <= 10: 11
3
```

Only assignment writes. Changing a list or dict in place stores nothing and emits nothing, so assign a new object:

```python
internal = qconfig.get_config(InternalConfig)
internal.recent_files = [*internal.recent_files, "run_01.csv"]
```

The slot connected in the first example reports the assignment:

```text
changed: Internal recent_files ['run_01.csv']
```

`QSettings` writes to disk or registry at intervals and when the application exits. Call `sync()` when the main
window closes to force the write.

A value is only in the store after it was assigned. Defaults stay in your code, so a default you change in a later
release reaches every user who never set that value.

## Types that survive the store

`QSettings` backends return `str` for most scalars (INI) or `"true"`/`"false"` for booleans (Windows registry), and
a one-element string list comes back as a `str`. The package converts stored values back to: `bool`, `int`,
`float`, `str`, `bytes`, `decimal.Decimal`, `pathlib.Path`, `QByteArray`, `Enum` subclasses (by value, then by
name), `X | None`, `Literal`, `list[T]`, `tuple[T, ...]`, `tuple[A, B]`, `set[T]` and `dict[K, V]`. Enums are
stored by `.value`, `Decimal` and `Path` as `str`.

A stored value that cannot be converted, or that the field's `converter` or `validator` rejects, is replaced by the
default when the group is loaded. The package logs a warning on the `pyside_config` logger that names the key and
the value.

## Show the dialog

`SettingsDialog` has one tab per visible group that has at least one editor, and the buttons OK, Cancel, Apply and
Restore Defaults.

- Edits stay in the dialog until OK or Apply. Cancel discards them.
- OK and Apply check every edited value against its field first. If one is invalid, nothing is assigned, the card
  shows the error in place of its description, and the dialog stays open.
- Restore Defaults and the reset button of a card show defaults in the editors. They are assigned by OK or Apply
  like any other edit.
- An editor you have not touched follows changes made to the setting elsewhere while the dialog is open.

The dialog sets no modality, size or `WA_DeleteOnClose`. Choose them where you show it:

```python
dialog = qconfig.SettingsDialog(exclude=[ExportConfig])
dialog.setWindowTitle("Preferences")
dialog.resize(800, 600)
dialog.open()  # window-modal; show() gives a non-modal dialog
```

To place a group in a window of your own, use `GroupPage`, the widget the dialog's tabs are made of:

```python
page = qconfig.GroupPage(PlotConfig)
page.sig_modified.connect(lambda modified: print("modified:", modified))
page.editor_widget("click_radius").setProperty("value", 45)
page.apply()
print(plot.click_radius)
```

```text
modified: True
changed: Plot click_radius 45
modified: False
45
```

## Editor widgets

The dialog reads, writes and watches an editor through its Qt USER property, the property `QDataWidgetMapper` and
item delegates use. Every widget with a writable USER property that has a notify signal works without
configuration. That covers `QSpinBox`, `QDoubleSpinBox`, `QSlider`, `QCheckBox`, `QLineEdit`, `QPlainTextEdit`,
`QKeySequenceEdit`, `QDateTimeEdit` and their subclasses, and pyside-widgets' `EnumComboBox`, `DecimalSpinBox` and
`AnimatedToggleSwitch`.

Three Qt widgets have a USER property that is not the value you want to store. The package registers hooks for
them: `QComboBox` uses the current item's data (falling back to its text), `QFontComboBox` the `QFont`, and
`QTextEdit` the plain text.

An editor receives the stored form of a value: an enum member as its `.value`, a `Path` or `Decimal` as `str`. What
the editor returns is converted to the field's type when it is applied. A `Path` field therefore works with a
`QLineEdit`.

For a widget without a fitting USER property, register hooks once for its class, or pass `hooks=` to one field:

```python
class ColorButton(QtWidgets.QPushButton):
    colorChanged = QtCore.Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._color = "#000000"

    def color(self) -> str:
        return self._color

    def setColor(self, color: str) -> None:
        if color != self._color:
            self._color = color
            self.colorChanged.emit(color)


qconfig.register_editor_hooks(ColorButton, qconfig.EditorHooks.from_names("colorChanged", "color", "setColor"))
```

The three names are the change signal, the getter and the setter, in that order.

## Reset and reload

| Function | Effect |
|---|---|
| `sync()` | Flush pending writes to permanent storage. |
| `restore_defaults(*groups)` | Remove the stored values of the given groups, or of all registered groups. The instances return to their defaults and `sig_value_changed` fires for each changed field. |
| `clear_store()` | Delete everything in the store, including keys the package never wrote, then reload. Needs no registered group, so it can run before your config module is imported. |
| `reload()` | Read the store again into the existing instances, for example after another process changed it. |

## List the declared settings

`iter_fields` yields one `FieldInfo` per field without creating an instance or reading the store. Use it to
generate documentation or to test that your documentation matches the declarations.

```python
for field in qconfig.iter_fields(include_hidden=False):
    print(f"{field.group}/{field.name}: {field.label} (default {field.default!r}, editor: {field.has_editor})")
```

```text
Plot/click_radius: Click radius (default 20, editor: True)
Plot/show_grid: Show grid (default True, editor: True)
Plot/last_folder: Last folder (default '', editor: False)
Export/decimals: Decimals (default 3, editor: True)
```

`group_info(PlotConfig)` returns the group's `name`, `title`, `hidden` flag and class; `groups()` returns that for
every registered group.

## Test an application that uses pyside-config

Point the package at a temporary INI file before the first `get_config` call. If one of your modules calls
`get_config` at import time, call `configure` before you import that module. No organization or application name is
needed then, and the user's real settings are never read or written.

```python
import tempfile
from pathlib import Path

settings_file = Path(tempfile.mkdtemp()) / "settings.ini"
qconfig.configure(lambda: QtCore.QSettings(str(settings_file), QtCore.QSettings.Format.IniFormat))
```

Instances that already exist keep their values when the store is replaced. Call `reload()` to fill them from the
new store.

Call `restore_defaults()` between tests so that one test's settings do not reach the next. Tests that declare groups
of their own call `clear_registry()` to remove them again.

## Known limits

- Changing a list or dict value in place is not detected. Assign a new object.
- Config instances and the signal object belong to the GUI thread. Read and assign settings there.
- Labels, descriptions and titles are plain strings fixed when the class is declared. They do not follow a
  `QTranslator` installed later.
- `clear_store()` deletes every key of the application's `QSettings`, not only the keys of registered groups.

## Upgrade from 0.2

[CHANGELOG.md](CHANGELOG.md) lists every removed name with its replacement.

## Development

```console
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check . && uv run pyright
```

`tests/test_readme.py` runs every `python` block of this file in order and compares the output with the `text`
blocks.
