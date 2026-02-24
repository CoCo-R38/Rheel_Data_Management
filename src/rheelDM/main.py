from __future__ import annotations

from pathlib import Path
from datetime import datetime, date, time
from typing import Any, get_origin, get_args, Union
import ast, types, copy


# =========================================================
# Type Registry
# =========================================================

class TypeRegistry:
    """
    Registry for custom types.

    Allows registering custom serializer/deserializer pairs
    for special Python types.

    Example:
        registry.register(
            "datetime",
            datetime,
            lambda v: f'"{v.isoformat()}"',
            lambda v: datetime.fromisoformat(v.strip('"'))
        )
    """

    def __init__(self):
        self._registry: dict[str, tuple[type, callable, callable]] = {}

    def register(self, name: str, typ: type, serializer, deserializer):
        """Register a new custom type."""
        self._registry[name] = (typ, serializer, deserializer)

    def serialize(self, value: Any) -> str:
        """Convert a Python value to its RDM string representation."""
        for name, (typ, serializer, _) in self._registry.items():
            if isinstance(value, typ):
                return serializer(value)
        return repr(value)

    def deserialize(self, value_str: str, typ: type):
        """Convert RDM string representation back to Python object."""
        for _, (registered_type, _, deserializer) in self._registry.items():
            if typ is registered_type:
                return deserializer(value_str)
        return ast.literal_eval(value_str)


registry = TypeRegistry()

registry.register(
    "datetime",
    datetime,
    lambda v: f'"{v.isoformat()}"',
    lambda v: datetime.fromisoformat(v.strip('"'))
)

registry.register(
    "date",
    date,
    lambda v: f'"{v.isoformat()}"',
    lambda v: date.fromisoformat(v.strip('"'))
)

registry.register(
    "time",
    time,
    lambda v: f'"{v.isoformat()}"',
    lambda v: time.fromisoformat(v.strip('"'))
)

registry.register(
    "Path",
    Path,
    lambda v: f'"{str(v)}"',
    lambda v: Path(v.strip('"'))
)


# =========================================================
# Safe Type Parsing
# =========================================================

SAFE_TYPES = {
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "list": list,
    "set": set,
    "tuple": tuple,
    "dict": dict,
    "datetime": datetime,
    "date": date,
    "time": time,
    "Path": Path,
    "NoneType": type(None),
}


def parse_type(type_str: str):
    """Safely parse a type string like 'list[str | int]'."""
    return eval(type_str, SAFE_TYPES)


# =========================================================
# Section
# =========================================================

class Section:
    """
    Represents a single section inside an Obj.

    Provides type-safe get/set methods, arithmetic operations for numbers
    and extension operations for strings, lists, sets, dicts, and Paths.

    Usage examples:

        sec = obj.section("user123")
        sec.set("score", int, 10)           # 10
        sec.add("score", 5)                 # 15
        sec.add("score", -3)                # 12
        sec.set("name", str, "CoCo")        # "CoCo"
        sec.extend("name", "Bot")           # "CoCoBot"
        sec.set("items", list, [1,2])       # [1,2]
        sec.extend("items", 3)              # [1,2,3]
        sec.extend("items", [4,5])          # [1,2,3,4,5]
        sec.set("tags", set, {1,2})         # {1,2}
        sec.extend("tags", 3)               # {1,2,3}
        sec.extend("tags", {4,5})           # {1,2,3,4,5}
        sec.set("config", dict, {"a":1})    # {"a": 1}
        sec.extend("config", {"b":2})       # {"a": 1, "b": 2}
        sec.set("joined", datetime.datetime.now())
        sec.add("joined", 3600)             # adds 3600 seconds
        sec.set("path", Path("/tmp"))       # Path("/tmp")
        sec.extend("path", "logs")          # Path("/tmp/logs")

        sec.delete("score")                 # remove key
    """

    def __init__(self, name: str):
        self.name = name
        self._items: dict[str, tuple[type, Any]] = {}

    def set(self, key: str, typ: type, value: Any, overwrite=True):
        """
        Set a key with strict type validation. Mutable values (`list`, `dict`, `set`) will be deep-copied to prevent external modifications after setting.

        `overwrite=False` will prevent overwriting existing keys, raising an error instead.
        """
        if not overwrite and key in self._items:
            raise KeyError(f"{key} already exists in section {self.name}")
        if isinstance(value, (list, dict, set)):
            value = copy.deepcopy(value)

        self._validate(value, typ)
        self._items[key] = (typ, value)

    def get(self, key: str, default: Any = KeyError) -> Any:
        """Retrieve a value by key. Returns a copy of default if key does not exist. Raises KeyError if key is missing and no default is provided."""
        val = self._items.get(key, (None, copy.deepcopy(default)))[1]
        if val is KeyError:
            raise KeyError(f"\"{key}\" does not exist in section {self.name}")
        else:
            return val

    def delete(self, key: str):
        """Remove a key from the section."""
        if key in self._items:
            del self._items[key]

    def add(self, key: str, value: Any):
        """
        Add or subtract a value for numbers or datetime.

        Works for int, float, or datetime (adds seconds as timedelta).
        Negative numbers perform subtraction.
        """
        if key not in self._items:
            raise KeyError(f"{key} does not exist in section {self.name}")
        typ, current = self._items[key]

        if typ in (int, float):
            self._items[key] = (typ, current + value)
        elif typ is datetime:
            import datetime as dt
            self._items[key] = (typ, current + dt.timedelta(seconds=value))
        else:
            raise TypeError(f"Cannot add to type {typ}")

    def multiply(self, key: str, factor: int | float):
        """
        Multiply a numeric value by a factor.

        Works for int and float types. Fractional values act as division.

        Raises:
            TypeError if the current value is not int or float.
        """
        if key not in self._items:
            raise KeyError(f"{key} does not exist in section {self.name}")
        typ, value = self._items[key]
        if typ not in (int, float):
            raise TypeError(f"Cannot multiply non-numeric type {typ}")
        self._items[key] = (typ, value * factor)

    def extend(self, key: str, value: Any):
        """
        Dynamically extend or combine values based on type:

            str       -> concatenate
            list      -> append item or concatenate list
            set       -> add item or union with set
            dict      -> merge dictionaries
            Path      -> join with string or Path
        """
        if key not in self._items:
            raise KeyError(f"{key} does not exist in section {self.name}")
        typ, current = self._items[key]

        if typ is str:
            if not isinstance(value, str):
                raise TypeError("Can only extend str with str")
            self._items[key] = (typ, current + value)

        elif typ is list:
            if isinstance(value, list):
                self._items[key] = (typ, current + value)
            else:
                self._items[key] = (typ, current + [value])

        elif typ is set:
            if isinstance(value, set):
                self._items[key] = (typ, current.union(value))
            else:
                self._items[key] = (typ, current | {value})

        elif typ is dict:
            if not isinstance(value, dict):
                raise TypeError("Can only extend dict with dict")
            self._items[key] = (typ, {**current, **value})

        elif typ is Path:
            from pathlib import Path
            if isinstance(value, (str, Path)):
                self._items[key] = (typ, current / value)
            else:
                raise TypeError("Can only extend Path with str or Path")

        else:
            raise TypeError(f"Cannot extend type {typ}")

    # -----------------------
    # Type Validation
    # -----------------------

    def _validate(self, value: Any, typ: type):
        origin = get_origin(typ)
        args = get_args(typ)

        if origin in (Union, types.UnionType):
            for option in args:
                try:
                    self._validate(value, option)
                    return
                except TypeError:
                    continue
            raise TypeError(f"{value} does not match any type in {typ}")

        if origin is None:
            if not isinstance(value, typ):
                raise TypeError(f"{value} is not {typ}")
            return

        if origin in (list, set, tuple):
            if not isinstance(value, origin):
                raise TypeError(f"Expected {origin.__name__}")
            for v in value:
                self._validate(v, args[0])
            return

        if origin is dict:
            if not isinstance(value, dict):
                raise TypeError("Expected dict")
            key_t, val_t = args
            for k, v in value.items():
                self._validate(k, key_t)
                self._validate(v, val_t)
            return

        raise TypeError(f"Unsupported type {typ}")

    # -----------------------
    # Serialization
    # -----------------------

    def serialize(self) -> list[str]:
        lines = [f"[{self.name}]"]

        max_key = max((len(k) for k in self._items), default=0)
        max_type = max((len(self._type_name(t)) for t, _ in self._items.values()), default=0)

        for key, (typ, value) in self._items.items():
            key_pad = key.ljust(max_key)
            type_name = self._type_name(typ)
            type_pad = type_name.ljust(max_type)
            value_str = registry.serialize(value)

            lines.append(f"{key_pad} : {type_pad} = {value_str}")

        return lines

    def _type_name(self, typ: type) -> str:
        origin = get_origin(typ)
        args = get_args(typ)

        if origin in (Union, types.UnionType):
            return " | ".join(self._type_name(a) for a in args)

        if origin is None:
            return typ.__name__

        inner = ", ".join(self._type_name(a) for a in args)
        return f"{origin.__name__}[{inner}]"

    @classmethod
    def from_lines(cls, name: str, lines: list[str]):
        """Create Section from RDM file lines."""
        section = cls(name)

        for raw_line in lines:
            line = raw_line.split("#", 1)[0].strip()
            if not line:
                continue

            left, value_str = line.split("=", 1)
            key_part, type_part = left.split(":", 1)

            key = key_part.strip()
            type_str = type_part.strip()
            value_str = value_str.strip()

            typ = parse_type(type_str)
            value = registry.deserialize(value_str, typ)

            section._items[key] = (typ, value)

        return section


# =========================================================
# Obj
# =========================================================

class Obj:
    """
    Main container for RDM data.

    Example:
        obj = Obj.load("config.rdm", default={"user": {"name": ("str", "CoCo")}})
        obj.section("user").set("score", int, 42)
        obj.save("config.rdm")
    """

    def __init__(self):
        self._sections: dict[str, Section] = {}

    def section(self, name: str) -> Section:
        """Access or create a section."""
        if name not in self._sections:
            self._sections[name] = Section(name)
        return self._sections[name]

    def save(self, filename: str | Path):
        """
        Save object to file.
        """
        path = Path(filename)
        if path.suffix != ".rdm":
            path = path.with_suffix(".rdm")

        lines = []
        for section in self._sections.values():
            lines.extend(section.serialize())
            lines.append("")

        path.write_text("\n".join(lines).rstrip())

    @classmethod
    def load(cls, filename: str | Path, default: dict | Obj | None = None) -> Obj:
        """
        Load an RDM file.

        If file does not exist:
            - If default is provided, return a copy of default
            - Else return empty Obj
        """
        path = Path(filename)
        if path.suffix != ".rdm":
            path = path.with_suffix(".rdm")

        if not path.exists():
            if isinstance(default, Obj):
                return copy.deepcopy(default)
            if isinstance(default, dict):
                return cls.from_dict(default)
            return cls()

        content = path.read_text().splitlines()

        obj = cls()
        current_name = None
        buffer = []

        for raw_line in content:
            stripped = raw_line.strip()

            if not stripped or stripped.startswith("#"):
                continue

            if stripped.startswith("[") and stripped.endswith("]"):
                if current_name:
                    obj._sections[current_name] = Section.from_lines(current_name, buffer)
                    buffer = []
                current_name = stripped[1:-1]
            else:
                buffer.append(raw_line)

        if current_name:
            obj._sections[current_name] = Section.from_lines(current_name, buffer)

        return obj

    @classmethod
    def from_dict(cls, data: dict) -> Obj:
        """
        Create Obj from a nested dictionary.

        Format:
            {
                "section": {
                    "key": (type, value)
                }
            }
        """
        obj = cls()
        for section_name, items in data.items():
            section = obj.section(section_name)
            for key, (typ, value) in items.items():
                section.set(key, typ, value)
        return obj