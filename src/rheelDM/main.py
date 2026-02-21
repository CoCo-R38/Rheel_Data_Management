from __future__ import annotations

from pathlib import Path
from datetime import datetime, date, time
from typing import Any, get_origin, get_args, Union
import ast
import types


# =========================================================
# Type Registry
# =========================================================

class TypeRegistry:
    def __init__(self):
        self._registry: dict[str, tuple[type, callable, callable]] = {}

    def register(self, name: str, typ: type, serializer, deserializer):
        self._registry[name] = (typ, serializer, deserializer)

    def serialize(self, value: Any) -> str:
        for name, (typ, serializer, _) in self._registry.items():
            if isinstance(value, typ):
                return serializer(value)
        return repr(value)

    def deserialize(self, value_str: str, typ: type):
        for name, (registered_type, _, deserializer) in self._registry.items():
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
}


def parse_type(type_str: str):
    return eval(type_str, SAFE_TYPES)


# =========================================================
# Section
# =========================================================

class Section:

    def __init__(self, name: str):
        self.name = name
        self._items: dict[str, tuple[type, Any]] = {}

    # -----------------------
    # Public API
    # -----------------------

    def set(self, key: str, typ: type, value: Any):
        self._validate(value, typ)
        self._items[key] = (typ, value)

    def get(self, key: str):
        return self._items[key][1]

    # -----------------------
    # Type Validation
    # -----------------------

    def _validate(self, value: Any, typ: type):
        origin = get_origin(typ)
        args = get_args(typ)

        # Union (str | int)
        if origin in (Union, types.UnionType):
            for option in args:
                try:
                    self._validate(value, option)
                    return
                except TypeError:
                    continue
            raise TypeError(f"{value} does not match any type in {typ}")

        # Normal type
        if origin is None:
            if not isinstance(value, typ):
                raise TypeError(f"{value} is not {typ}")
            return

        if origin is list:
            if not isinstance(value, list):
                raise TypeError("Expected list")
            for v in value:
                self._validate(v, args[0])
            return

        if origin is set:
            if not isinstance(value, set):
                raise TypeError("Expected set")
            for v in value:
                self._validate(v, args[0])
            return

        if origin is tuple:
            if not isinstance(value, tuple):
                raise TypeError("Expected tuple")
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

    # -----------------------
    # Parsing
    # -----------------------

    @classmethod
    def from_lines(cls, name: str, lines: list[str]):
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

    def __init__(self):
        self._sections: dict[str, Section] = {}

    def section(self, name: str) -> Section:
        if name not in self._sections:
            self._sections[name] = Section(name)
        return self._sections[name]

    def save(self, filename: str):
        if not filename.endswith(".rdm"):
            filename += ".rdm"

        lines = []

        for section in self._sections.values():
            lines.extend(section.serialize())
            lines.append("")

        Path(filename).write_text("\n".join(lines).rstrip())

    @classmethod
    def load(cls, filename: str):
        content = Path(filename).read_text().splitlines()

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