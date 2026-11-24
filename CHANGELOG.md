# Changelog

This file lists what changed between releases of pyside-config, for developers who upgrade an application that uses
the package. Each release names the breaking changes first, with the replacement for every removed name.

## 0.3.0 (2026-11-24)

Verified with PySide6 6.12.0 and pyside-widgets 0.5.0 on Python 3.15.

### Breaking changes

| Before | After |
|---|---|
| `EditorWidgetInfo("Label", factory, ...)` passed as `config_field(editor=...)` | `config_field(label="Label", editor=factory, icon=..., hooks=...)`. `editor` is a zero-argument callable returning the widget. `label` defaults to the field name with underscores as spaces. |
| `pyside_config.helpers`: `make_spin_box_info`, `make_double_spin_box_info`, `make_decimal_spin_box_info`, `make_line_edit_info`, `make_check_box_info`, `make_combo_box_info` | Removed. Set Qt properties in the constructor: `editor=lambda: QtWidgets.QSpinBox(minimum=0, maximum=1000, suffix=" px")`. |
| The helpers changed widgets you did not ask them to: frame off, spin box range 0 to 1,000,000, line edit clear button on | Nothing but your `editor` callable configures the widget. Drop `hasFrame=True` and similar arguments that undid those defaults. Pass `clearButtonEnabled=True` or a range where you relied on them. |
| `pyside_config.properties` (`SpinBoxProperties`, `LineEditProperties`, ...), `SETTER_KEY` | Removed. |
| `EditorWidgetInfo(sig_value_changed=..., set_value_method=..., get_value_method=...)` | `config_field(hooks=EditorHooks.from_names(signal, getter, setter))`. The order is signal, getter, setter. |
| `DEFAULT_HOOKS`, `hooks_for` | Removed from the public API. Hooks come from the widget's Qt USER property. Use `register_editor_hooks` for a class without a fitting one. |
| `QAction` as an editor | Removed. It could not be placed on a card. |
| `EDITOR_KEY`, `DESCRIPTION_KEY`, `QTYPE_KEY` and `attrs.field(metadata={EDITOR_KEY: ...})` | Removed. Declare fields with `config_field`. |
| `create_editor(**kwargs)` and `inst.create_editor(**kwargs)` forwarded keyword arguments to every widget factory | Removed. Editor callables take no arguments. |
| `inst.create_editor()` returned a `QScrollArea` that wrote every edit at once | `GroupPage(ConfigClass)`. Edits are assigned by `page.apply()`. |
| `inst.restore_defaults()`, `inst.to_qsettings()`, `Class.from_qsettings()`, `Class.__group_prefix__`, `Class.__hidden__`, `ConfigInstance` | Removed. Nothing is added to your class. Use `restore_defaults(Class)`, `reload()`, `group_info(Class).name` and `group_info(Class).hidden`. |
| `groups()` returned `{name: instance}` | Returns a list of `GroupInfo(name, title, hidden, config_class)`. Get an instance with `get_config`. |
| `unregister(name)` | Also accepts the class. |
| `update_value(group, key, value)` | `setattr(get_config(group), key, value)`. |
| `create_snapshot()`, `restore_snapshot()` | Removed. The dialog keeps edits to itself until they are applied, so there is nothing to roll back. |
| `coerce` | No longer exported. |
| `FieldInfo.label` was `None` for a field without an editor | `FieldInfo.label` is always a `str`. Use the new `FieldInfo.has_editor`. |
| A `@config` class read `QSettings` when it was declared | The store is read on the first `get_config` call. `configure()` and the organization name must be set before that call, not before the declaration. |
| A second instance, such as `PlotConfig()`, wrote to `QSettings` on assignment | Only the instance returned by `get_config` writes and emits. |
| `sig_value_changed` fired before the instance held the new value | Fires after. A slot that reads the instance sees the new value. |
| `save()` wrote every field, including untouched defaults | `sync()` only flushes. A value is in the store only after it was assigned, so a default changed in code reaches users who never set the value. |
| `reset()` wrote the defaults to the store | `restore_defaults()` removes the keys. |
| `clean()` left the instances unchanged | `clear_store()` also reloads the instances, which return to their defaults. |
| A field without `default` or `factory` | `TypeError` when the class is declared. |
| Annotations that could not be resolved switched type conversion off for the whole class without a message | `TypeError` when the class is declared. Import the type at runtime or pass `qtype=`. |
| `coerce(2.7, int)` returned `2` | `ValueError`. Whole numbers such as `"5.0"` still convert. |
| A group without editors got an empty tab | No tab. |
| `get_config`, `update_value` and `unregister` raised different exceptions for an unknown group | Every lookup raises `KeyError` with the group name in the message. |

### Deprecated

Each of these still works, emits `DeprecationWarning`, and is removed in 0.4.

| Deprecated | Use |
|---|---|
| `create_editor(parent, exclude, window_title, include_hidden=...)` | `SettingsDialog(parent, exclude=..., include_hidden=...)`. `create_editor` still returns a modal 800x600 dialog that is deleted on close. `SettingsDialog` sets none of the three. |
| `save()` | `sync()` |
| `reset(exclude=...)` | `restore_defaults(*groups)` |
| `clean(exclude=...)` | `clear_store()` |
| `config(group_name=...)` | `config(group=...)` |

### Added

- `SettingsDialog`, a `QDialog` subclass with OK, Cancel, Apply and Restore Defaults. Apply is enabled while there is
  an edit to assign.
- `GroupPage`, the widget of one group, for embedding in your own window: `values()`, `is_modified()`, `validate()`,
  `apply()`, `revert()`, `restore_defaults()`, `editor_widget(name)` and the signal `sig_modified`.
- `config(title=...)`: a tab title separate from the storage key.
- `group_info()`, `GroupInfo`, `reload()`, `clear_registry()`.
- `@config` is a `typing.dataclass_transform`, so type checkers know the fields and the constructor of a config
  class.
- Any widget with a writable Qt USER property that has a notify signal works as an editor without registration.
- `tuple[A, B]` fields: each position is converted to its own type.
- A CI workflow (`.github/workflows/ci.yml`) and a test that runs the README.

### Fixed

- A stored value that a field's `validator` or `converter` rejected raised inside `@config` and stopped the
  application at import. It is now replaced by the default, with a warning on the `pyside_config` logger. The same
  warning is logged for a value that cannot be converted to the field's type, which used to be dropped silently.
- An invalid value in the dialog raised after the dialog had closed and left the edits half assigned. OK and Apply
  now validate everything first, show the error on the card and keep the dialog open.
- A field whose type differs from what its widget accepts, such as a `Path` shown in a `QLineEdit`, raised
  `TypeError` when the dialog was built.
- `uv.lock` pinned pyside-widgets 0.4.0, with which the test suite failed.

## 0.2.1

Adapted to pyside-widgets 0.5.0 (`EnumComboBox.get_current_enum`).

## 0.2.0

Rewrite: typed `get_config`, type conversion on load and on assignment, a settings dialog that applies edits on OK,
`sig_value_changed`, `iter_fields`.
