import enum
import logging
from pathlib import Path
from typing import Any, assert_type, cast

import attrs
import pytest
from conftest import ini_store, restart
from PySide6 import QtCore

import pyside_config as qconfig
from pyside_config import config, config_field, get_config
from pyside_config._settings import coerce

type Changes = list[tuple[str, str, object]]


class Method(enum.StrEnum):
    Fast = "fast"
    Slow = "slow"


class Level(enum.IntEnum):
    Low = 1
    High = 2


def declare_group(name: str = "Demo", hidden: bool = False, count_default: int = 3) -> Any:
    @config(group=name, hidden=hidden)
    class Demo:
        count: int = config_field(default=count_default, description="A count")
        ratio: float = config_field(default=0.5)
        enabled: bool = config_field(default=False)
        method: Method = config_field(default=Method.Fast)
        level: Level = config_field(default=Level.Low)
        tags: list[str] = config_field(factory=list)
        blob: QtCore.QByteArray = config_field(factory=QtCore.QByteArray)
        maybe: int | None = config_field(default=None)
        converted: str = config_field(default="x", converter=str.upper)
        limited: int = config_field(default=1, validator=attrs.validators.le(10))

    return Demo


# --- coerce -------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "type_", "expected"),
    [
        ("5", int, 5),
        ("5.0", int, 5),
        (5.0, int, 5),
        (True, int, 1),
        ("true", bool, True),
        ("false", bool, False),
        ("0", bool, False),
        (1, bool, True),
        ("2.5", float, 2.5),
        (None, str, ""),
        (7, str, "7"),
        ("fast", Method, Method.Fast),
        ("Slow", Method, Method.Slow),
        ("2", Level, Level.High),
        (2, Level, Level.High),
        (None, list[str], []),
        ("one", list[str], ["one"]),
        ("", list[str], []),
        (["1", "2"], list[int], [1, 2]),
        (("a",), tuple[str, ...], ("a",)),
        (["1", "a"], tuple[int, str], (1, "a")),
        (None, int | None, None),
        ("4", int | None, 4),
        ("b", str | None, "b"),
        (None, QtCore.QByteArray, QtCore.QByteArray()),
        (b"ab", QtCore.QByteArray, QtCore.QByteArray(b"ab")),
        ("c:/x", Path, Path("c:/x")),
        ("hi", str, "hi"),
    ],
)
def test_coerce(value: Any, type_: Any, expected: Any) -> None:
    assert coerce(value, type_) == expected


@pytest.mark.parametrize(
    ("value", "type_"),
    [
        ("maybe", bool),
        ("x", int),
        (2.7, int),
        ("5.9", int),
        (float("inf"), int),
        ("nope", Method),
        (None, Method),
        (["1"], tuple[int, str]),
    ],
)
def test_coerce_rejects(value: Any, type_: Any) -> None:
    with pytest.raises((ValueError, TypeError)):
        coerce(value, type_)


# --- declaration and registry --------------------------------------------------------------------------------------


def test_defaults_when_store_is_empty() -> None:
    Demo = declare_group()
    demo = get_config(Demo)
    assert demo.count == 3
    assert demo.method is Method.Fast
    assert demo.tags == []
    assert demo.blob == QtCore.QByteArray()
    assert demo.maybe is None
    assert demo.converted == "X"  # the converter also runs on the default
    assert get_config("Demo") is demo
    assert get_config(Demo) is demo


def test_declaring_a_group_does_not_touch_the_store(ini_path: Path) -> None:
    created: list[QtCore.QSettings] = []

    def factory() -> QtCore.QSettings:
        created.append(ini_store(ini_path))
        return created[-1]

    qconfig.configure(factory)
    Demo = declare_group()
    assert list(qconfig.iter_fields())  # introspection needs no store either
    assert created == []
    get_config(Demo)
    assert len(created) == 1


def test_get_config_unknown() -> None:
    with pytest.raises(KeyError, match="No config group named 'Nope'"):
        get_config("Nope")

    class NotRegistered: ...

    with pytest.raises(KeyError, match="NotRegistered is not a registered config class"):
        get_config(NotRegistered)
    with pytest.raises(KeyError):
        qconfig.group_info("Nope")
    with pytest.raises(KeyError):
        qconfig.unregister("Nope")
    with pytest.raises(KeyError):
        qconfig.restore_defaults("Nope")


def test_duplicate_group_name_raises() -> None:
    declare_group()
    with pytest.raises(ValueError, match="already registered"):
        declare_group()


def test_field_without_default_raises() -> None:
    with pytest.raises(TypeError, match="NoDefault.count needs a default"):

        @config
        class NoDefault:
            count: int = config_field()


def test_unresolvable_annotation_raises() -> None:
    source = (
        "from __future__ import annotations\n"
        "from typing import TYPE_CHECKING\n"
        "if TYPE_CHECKING:\n"
        "    from pathlib import Path\n"
        "@config(group='Unresolved')\n"
        "class Unresolved:\n"
        "    count: int = config_field(default=3)\n"
        "    folder: Path | None = config_field(default=None)\n"
    )
    with pytest.raises(TypeError, match="Cannot resolve the annotation of Unresolved.count"):
        exec(source, {"config": config, "config_field": config_field})


def test_group_info_title_and_registry() -> None:
    Demo = declare_group()

    @config(group="Secret", title="Hidden things", hidden=True)
    class Secret:
        token: str = config_field(default="")

    assert qconfig.group_info(Demo) == qconfig.GroupInfo("Demo", "Demo", False, Demo)
    assert qconfig.group_info("Secret") == qconfig.GroupInfo("Secret", "Hidden things", True, Secret)
    assert [g.name for g in qconfig.groups()] == ["Demo", "Secret"]

    qconfig.unregister(Demo)
    assert [g.name for g in qconfig.groups()] == ["Secret"]
    declare_group()  # the name can be used again
    qconfig.clear_registry()
    assert qconfig.groups() == []


def test_get_config_is_typed() -> None:
    @config(group="Typed")
    class Typed:
        count: int = config_field(default=1)
        folder: Path | None = config_field(default=None)

    typed = get_config(Typed)
    assert_type(typed, Typed)  # checked by pyright; a no-op at runtime
    assert_type(typed.count, int)
    assert_type(typed.folder, Path | None)
    assert_type(Typed(count=2).count, int)  # the constructor is known as well
    assert typed.count == 1


def test_bare_decorator_uses_the_class_name() -> None:
    @config
    class Bare:
        count: int = config_field(default=1)

    assert qconfig.group_info(Bare).name == "Bare"
    assert get_config("Bare").count == 1


def test_unregistered_base_class_contributes_fields(fresh_store: QtCore.QSettings) -> None:
    @config(register=False)
    class Base:
        shared: int = config_field(default=1)

    @config(group="Child")
    class Child(Base):
        own: int = config_field(default=2)

    assert [g.name for g in qconfig.groups()] == ["Child"]
    child = get_config(Child)
    child.shared = 5
    assert fresh_store.value("Child/shared") == 5


def test_group_name_is_a_deprecated_alias() -> None:
    with pytest.warns(DeprecationWarning, match="group_name"):

        @config(group_name="Old")
        class Old:
            count: int = config_field(default=1)

    assert qconfig.group_info(Old).name == "Old"


# --- assignment ----------------------------------------------------------------------------------------------------


def test_assignment_coerces_and_writes(fresh_store: QtCore.QSettings) -> None:
    demo = get_config(declare_group())
    demo.count = "7"  # the assignments are deliberately of the wrong static type
    demo.enabled = "true"
    demo.method = "slow"
    demo.level = "2"
    demo.tags = ("a", "b")
    assert demo.count == 7 and isinstance(demo.count, int)
    assert demo.enabled is True
    assert demo.method is Method.Slow
    assert demo.level is Level.High
    assert demo.tags == ["a", "b"]
    assert fresh_store.value("Demo/count") == 7
    assert fresh_store.value("Demo/method") == "slow"


def test_assignment_runs_converter() -> None:
    demo = get_config(declare_group())
    demo.converted = "abc"
    assert demo.converted == "ABC"


def test_assignment_rejects_bad_value(fresh_store: QtCore.QSettings, changes: Changes) -> None:
    demo = get_config(declare_group())
    with pytest.raises(ValueError):
        demo.count = "many"
    with pytest.raises(ValueError):
        demo.limited = 11
    assert (demo.count, demo.limited) == (3, 1)
    assert fresh_store.allKeys() == []
    assert changes == []


def test_signal_emitted_on_change_only(changes: Changes) -> None:
    demo = get_config(declare_group())
    demo.count = 3  # unchanged
    demo.count = 4
    demo.method = Method.Slow
    assert changes == [("Demo", "count", 4), ("Demo", "method", Method.Slow)]


def test_instance_holds_the_new_value_when_the_signal_arrives() -> None:
    demo = get_config(declare_group())
    seen: list[tuple[object, object]] = []

    def record(group: str, name: str, value: object) -> None:
        seen.append((value, demo.count))

    qconfig.signals().sig_value_changed.connect(record)
    demo.count = 4
    qconfig.signals().sig_value_changed.disconnect(record)
    assert seen == [(4, 4)]


def test_only_the_registered_instance_writes(fresh_store: QtCore.QSettings, changes: Changes) -> None:
    Demo = declare_group()
    get_config(Demo)
    copy = Demo()
    copy.count = "9"
    assert copy.count == 9  # still coerced and validated
    assert fresh_store.allKeys() == [] and changes == []


# --- persistence ---------------------------------------------------------------------------------------------------


def test_round_trip_through_ini(ini_path: Path) -> None:
    demo = get_config(declare_group())
    demo.count = 9
    demo.ratio = 1.25
    demo.enabled = True
    demo.method = Method.Slow
    demo.level = Level.High
    demo.tags = ["one"]  # one-element lists come back as a plain str from INI
    demo.blob = QtCore.QByteArray(b"\x00\x01geometry")
    demo.maybe = 12

    restart(ini_path)
    reloaded = get_config(declare_group())
    assert reloaded.count == 9
    assert reloaded.ratio == 1.25
    assert reloaded.enabled is True
    assert reloaded.method is Method.Slow
    assert reloaded.level is Level.High
    assert reloaded.tags == ["one"]
    assert reloaded.blob == QtCore.QByteArray(b"\x00\x01geometry")
    assert reloaded.maybe == 12


def test_unusable_stored_values_fall_back_to_the_default(
    fresh_store: QtCore.QSettings, caplog: pytest.LogCaptureFixture
) -> None:
    fresh_store.setValue("Demo/count", "garbage")  # cannot be coerced
    fresh_store.setValue("Demo/method", "unknown")  # not a member
    fresh_store.setValue("Demo/limited", 500)  # rejected by the validator
    fresh_store.setValue("Demo/converted", 5)  # the converter raises
    fresh_store.setValue("Demo/ratio", "1.5")  # fine

    with caplog.at_level(logging.WARNING, logger="pyside_config"):
        demo = get_config(declare_group())

    assert (demo.count, demo.method, demo.limited, demo.converted, demo.ratio) == (3, Method.Fast, 1, "X", 1.5)
    warned = " ".join(record.getMessage() for record in caplog.records)
    for path in ("Demo/count", "Demo/method", "Demo/limited", "Demo/converted"):
        assert path in warned
    assert "Demo/ratio" not in warned


def test_sync_does_not_write_defaults(fresh_store: QtCore.QSettings) -> None:
    get_config(declare_group())
    qconfig.sync()
    assert fresh_store.allKeys() == []


def test_changed_default_reaches_a_user_who_never_set_the_value(ini_path: Path) -> None:
    demo = get_config(declare_group())
    demo.ratio = 2.0  # the user changes one setting, the app shuts down
    restart(ini_path)

    upgraded = get_config(declare_group(count_default=35))  # the next release ships a new default
    assert upgraded.count == 35
    assert upgraded.ratio == 2.0


def test_restore_defaults(fresh_store: QtCore.QSettings, changes: Changes) -> None:
    demo = get_config(declare_group())
    other = get_config(declare_group("Other"))
    demo.count = 5
    demo.converted = "abc"
    other.count = 6
    changes.clear()

    qconfig.restore_defaults("Demo")
    assert (demo.count, demo.converted, other.count) == (3, "X", 6)
    assert fresh_store.allKeys() == ["Other/count"]  # the keys are removed, not overwritten with the default
    assert changes == [("Demo", "count", 3), ("Demo", "converted", "X")]

    qconfig.restore_defaults()
    assert other.count == 3 and fresh_store.allKeys() == []


def test_restore_defaults_of_a_group_that_was_never_loaded(fresh_store: QtCore.QSettings) -> None:
    fresh_store.setValue("Demo/count", 8)
    Demo = declare_group()
    qconfig.restore_defaults(Demo)
    assert fresh_store.allKeys() == []
    assert get_config(Demo).count == 3


def test_clear_store_removes_everything_and_reloads(fresh_store: QtCore.QSettings, changes: Changes) -> None:
    fresh_store.setValue("Foreign/key", 1)
    demo = get_config(declare_group())
    demo.count = 9
    changes.clear()

    qconfig.clear_store()
    assert fresh_store.allKeys() == []
    assert demo.count == 3
    assert changes == [("Demo", "count", 3)]

    qconfig.sync()  # shutting down afterwards writes nothing back
    assert fresh_store.allKeys() == []


def test_reload_reads_external_changes(ini_path: Path, changes: Changes) -> None:
    demo = get_config(declare_group())
    other_process = ini_store(ini_path)
    other_process.setValue("Demo/count", 12)
    other_process.sync()

    qconfig.reload()
    assert demo.count == 12
    assert changes == [("Demo", "count", 12)]


def test_deprecated_store_functions(fresh_store: QtCore.QSettings) -> None:
    demo = get_config(declare_group())
    other = get_config(declare_group("Other"))
    demo.count = 5
    other.count = 6

    with pytest.warns(DeprecationWarning, match="sync"):
        qconfig.save()
    assert sorted(fresh_store.allKeys()) == ["Demo/count", "Other/count"]

    with pytest.warns(DeprecationWarning, match="restore_defaults"):
        qconfig.reset(exclude=["Other"])
    assert (demo.count, other.count) == (3, 6)

    demo.count = 5
    with pytest.warns(DeprecationWarning, match="clear_store"):
        qconfig.clean(exclude=["Other"])
    assert fresh_store.childGroups() == ["Other"] and demo.count == 3

    with pytest.warns(DeprecationWarning, match="clear_store"):
        qconfig.clean()
    assert fresh_store.allKeys() == [] and other.count == 3


# --- introspection -------------------------------------------------------------------------------------------------


def test_iter_fields_and_hidden() -> None:
    @config(group="Shown")
    class Shown:
        click_radius: int = config_field(default=20, description="Radius", editor=lambda: cast(Any, None))
        named: int = config_field(default=1, label="Custom label")

    declare_group("Secret", hidden=True)

    visible = {f.name: f for f in qconfig.iter_fields(include_hidden=False)}
    assert set(visible) == {"click_radius", "named"}
    radius = visible["click_radius"]
    assert (radius.group, radius.type, radius.default, radius.description) == ("Shown", int, 20, "Radius")
    assert radius.label == "Click radius"  # derived from the field name
    assert radius.has_editor and radius.editable
    assert visible["named"].label == "Custom label"
    assert not visible["named"].has_editor and not visible["named"].editable

    assert {f.group for f in qconfig.iter_fields()} == {"Shown", "Secret"}
    assert all(f.hidden and not f.editable for f in qconfig.iter_fields() if f.group == "Secret")


def test_qtype_override(fresh_store: QtCore.QSettings) -> None:
    fresh_store.setValue("Q/value", "3")

    @config(group="Q")
    class Q:
        value: object = config_field(default=0, qtype=int)

    assert get_config(Q).value == 3


def test_plain_attrs_field_and_own_metadata() -> None:
    @config(group="Plain")
    class Plain:
        count: int = attrs.field(default=1)
        tagged: int = config_field(default=2, metadata={"unit": "px"})

    plain = get_config(Plain)
    plain.count = "4"  # type: ignore[assignment]
    assert plain.count == 4
    assert attrs.fields(Plain).tagged.metadata["unit"] == "px"
    assert [f.label for f in qconfig.iter_fields()] == ["Count", "Tagged"]


def test_editor_must_be_callable() -> None:
    with pytest.raises(TypeError, match="editor must be a zero-argument callable"):
        config_field(default=1, editor=cast(Any, "QSpinBox"))
