from __future__ import annotations
from pathlib import Path
from datetime import datetime, date, time, timezone, timedelta
from typing import Any, get_origin, get_args, Union, Optional
import ast, types, copy, json, configparser, importlib, inspect
try: import tomllib  # type: ignore
except ModuleNotFoundError: tomllib = None
try: import toml # type: ignore
except ModuleNotFoundError: toml = None
try: import yaml # type: ignore
except ModuleNotFoundError: yaml = None

# =========================================================
# Type Registry
# =========================================================

DEFAULT_TYPES = {
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "NoneType": type(None),
    "Optional": Union[type(None), Any],

    "list": list,
    "set": set,
    "tuple": tuple,
    "dict": dict,

    "datetime": datetime,
    "date": date,
    "time": time,

    "Path": Path,
}

def import_from_path(path: str):
    parts = path.split(".")

    for i in range(len(parts), 0, -1):
        module_path = ".".join(parts[:i])

        try:
            module = importlib.import_module(module_path)
            obj = module

            for part in parts[i:]:
                obj = getattr(obj, part)

            return obj

        except ModuleNotFoundError:
            continue

    raise ImportError(f"Cannot import {path}")

class TypeRegistry:
    """
    Simple in-memory type registry.

    Supports custom serializer/deserializer pairs.
    No persistence, no import issues, no circular dependencies.
    """

    _types: dict[str, type] = DEFAULT_TYPES.copy()
    _registry: dict[str, tuple[type, callable, callable]] = {}

    # -----------------------------------------------------

    @classmethod
    def register(cls, name: str, typ: type, serializer, deserializer):
        """
        Register a custom type.

        Example:
            TypeRegistry.register(
                "PartialEmoji",
                discord.PartialEmoji,
                lambda v: str(v),
                discord.PartialEmoji.from_str
            )
        """
        cls._types[name] = typ
        cls._registry[name] = (typ, serializer, deserializer)

    # -----------------------------------------------------

    @classmethod
    def clear_custom(cls):
        """Reset registry to default types."""
        cls._registry.clear()
        cls._types = DEFAULT_TYPES.copy()

    # -----------------------------------------------------

    @classmethod
    def serialize(cls, value):
        """Convert Python object to RDM string."""

        for typ, serializer, _ in cls._registry.values():
            if isinstance(value, typ):
                return serializer(value)

        return repr(value)

    # -----------------------------------------------------

    @classmethod
    def deserialize(cls, value_str, typ):
        """Convert RDM string back to Python object."""

        for registered_type, _, deserializer in cls._registry.values():
            origin = get_origin(typ) or typ
            if isinstance(origin, type) and issubclass(origin, registered_type):
                return deserializer(value_str)

        return ast.literal_eval(value_str)


TypeRegistry.register(
    "datetime",
    datetime,
    lambda v: v.isoformat(),
    datetime.fromisoformat
)

TypeRegistry.register(
    "date",
    date,
    lambda v: v.isoformat(),
    date.fromisoformat
)

TypeRegistry.register(
    "time",
    time,
    lambda v: v.isoformat(),
    time.fromisoformat
)

TypeRegistry.register(
    "Path",
    Path,
    str,
    Path
)


# =========================================================
# Safe Type Parsing
# =========================================================

def _convert_optional(type_str: str) -> str:
    """
    Converts:
        Optional[str]        → str | NoneType
        Optional[list[int]]  → list[int] | NoneType
        Optional[dict[str,int]] → dict[str,int] | NoneType
    """

    result = ""
    i = 0

    while i < len(type_str):
        if type_str.startswith("Optional[", i):
            i += len("Optional[")

            bracket_level = 1
            inner = ""

            while i < len(type_str) and bracket_level > 0:
                if type_str[i] == "[":
                    bracket_level += 1
                elif type_str[i] == "]":
                    bracket_level -= 1

                if bracket_level > 0:
                    inner += type_str[i]

                i += 1

            # Recursively handle nested Optional
            inner = _convert_optional(inner)

            result += f"{inner} | NoneType"
        else:
            result += type_str[i]
            i += 1

    return result

def parse_type(type_str: str):
    """
    Safely parse type strings like:
        list[str | int]
        Optional[str]
    """

    # ---- Convert Optional[T] → T | NoneType ----
    if "Optional[" in type_str:
        type_str = _convert_optional(type_str)

    return eval(type_str, TypeRegistry._types)

# =========================================================
# ExpiredKey Type
# =========================================================

class ExpiredKey:
    """
    Represents an expired temporary key.

    Contains metadata about the key and its expiration time.
    """

    def __init__(self, key: str, expired_at: datetime):
        self.key = key
        self.expired_at = expired_at

    def __repr__(self):
        return (
            f"<ExpiredKey key='{self.key}' "
            f"expired_at='{self.expired_at.isoformat()}'>"
        )

    def __bool__(self):
        """
        ExpiredKey evaluates to False in boolean context.
        """
        return False


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
        self._aliases: dict[str, str] = {}

    def set(self, key: str, typ: type, value: Any, overwrite=True):
        """
        Set a key with strict type validation. Mutable values (`list`, `dict`, `set`) will be deep-copied to prevent external modifications after setting.

        `overwrite=False` will prevent overwriting existing keys, raising an error instead.
        """
        keys = [k.strip() for k in key.split("|")]
        main_key = keys[0]

        if not overwrite:
            for k in keys:
                if k in self._aliases:
                    raise KeyError(f"{k} already exists")

        if isinstance(value, (list, dict, set)):
            value = copy.deepcopy(value)

        self._validate(value, typ)
        self._items[main_key] = (typ, value)

        for k in keys:
            self._aliases[k] = main_key

        # ensure main key always exists
        if main_key not in self._aliases:
            self._aliases[main_key] = main_key

    def get(self, key: str, default: Any = KeyError) -> Any:
        """Retrieve a value by key. Returns a copy of default if key does not exist. Raises KeyError if key is missing and no default is provided."""
        key = self._resolve_key(key)
        val = self._items.get(key, (None, copy.deepcopy(default)))[1]
        if val is KeyError:
            raise KeyError(f"\"{key}\" does not exist in section {self.name}")
        else:
            return val

    def delete(self, key: str):
        """Remove a key from the section."""
        key = self._resolve_key(key)
        aliases_to_remove = [k for k, v in self._aliases.items() if v == key]
        for k in aliases_to_remove:
            del self._aliases[k]

        del self._items[key]

    def add(self, key: str, value: Any):
        """
        Add or subtract a value for numbers or datetime.

        Works for int, float, or datetime (adds seconds as timedelta).
        Negative numbers perform subtraction.
        """
        key = self._resolve_key(key)
        if key not in self._items:
            raise KeyError(f"{key} does not exist in section {self.name}")
        typ, current = self._items[key]

        origin_type = get_origin(typ) or typ

        if origin_type in (int, float):
            self._items[key] = (typ, current + value)
        elif origin_type is datetime:
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
        key = self._resolve_key(key)
        if key not in self._items:
            raise KeyError(f"{key} does not exist in section {self.name}")
        typ, value = self._items[key]

        origin_type = get_origin(typ) or typ

        if origin_type not in (int, float):
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
        key = self._resolve_key(key)
        if key not in self._items:
            raise KeyError(f"{key} does not exist in section {self.name}")
        typ, current = self._items[key]

        origin_type = get_origin(typ) or typ

        if origin_type is str:
            if not isinstance(value, str):
                raise TypeError("Can only extend str with str")
            self._items[key] = (typ, current + value)

        elif origin_type is list:
            if isinstance(value, list):
                self._items[key] = (typ, current + value)
            else:
                self._items[key] = (typ, current + [value])

        elif origin_type is set:
            if isinstance(value, set):
                self._items[key] = (typ, current.union(value))
            else:
                self._items[key] = (typ, current | {value})

        elif origin_type is dict:
            if not isinstance(value, dict):
                raise TypeError("Can only extend dict with dict")
            self._items[key] = (typ, {**current, **value})

        elif origin_type is Path:
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

        # ------------------------------------------------
        # Union Types (str | int, Union[str, int])
        # ------------------------------------------------
        if origin in (Union, types.UnionType):
            for option in args:
                try:
                    self._validate(value, option)
                    return
                except TypeError:
                    pass
            raise TypeError(f"{value!r} does not match any type in {typ}")

        # ------------------------------------------------
        # Non-generic types
        # ------------------------------------------------
        if origin is None:
            if typ is Any:
                return

            if not isinstance(value, typ):
                raise TypeError(f"{value!r} is not {typ}")
            return

        # ------------------------------------------------
        # list[T], set[T], tuple[T]
        # ------------------------------------------------
        if origin in (list, set, tuple):
            if not isinstance(value, origin):
                raise TypeError(f"Expected {origin.__name__}, got {type(value).__name__}")

            if not args:
                return

            item_type = args[0]

            for v in value:
                self._validate(v, item_type)

            return

        # ------------------------------------------------
        # dict[K, V]
        # ------------------------------------------------
        if origin is dict:
            if not isinstance(value, dict):
                raise TypeError(f"Expected dict, got {type(value).__name__}")

            key_t, val_t = args

            for k, v in value.items():
                self._validate(k, key_t)
                self._validate(v, val_t)

            return

        # ------------------------------------------------
        # Unsupported typing construct
        # ------------------------------------------------
        raise TypeError(f"Unsupported type {typ}")

    # -----------------------
    # Serialization
    # -----------------------
    def _alias_string(self, main_key):
        return " | ".join(k for k, v in self._aliases.items() if v == main_key)

    def serialize(self) -> list[str]:
        lines = [f"[{self.name}]"]

        max_key = max((len(self._alias_string(k)) for k in self._items), default=0)
        max_type = max((len(self._type_name(t)) for t, _ in self._items.values()), default=0)

        for main_key, (typ, value) in self._items.items():
            aliases = [k for k, v in self._aliases.items() if v == main_key]
            key_str = " | ".join(aliases)
            key_pad = key_str.ljust(max_key)
            type_name = self._type_name(typ)
            type_pad = type_name.ljust(max_type)
            value_str = TypeRegistry.serialize(value)

            lines.append(f"{key_pad} : {type_pad} = {value_str}")

        return lines

    def _type_name(self, typ: type) -> str:
        origin = get_origin(typ)
        args = get_args(typ)

        # -------------------------
        # Handle Union / Optional
        # -------------------------
        if origin in (Union, types.UnionType):
            args_set = set(args)

            # Detect Optional[T] → Union[T, NoneType]
            if type(None) in args_set and len(args) == 2:
                non_none = [a for a in args if a is not type(None)][0]
                return f"Optional[{self._type_name(non_none)}]"

            # Fallback: normal union
            return " | ".join(self._type_name(a) for a in args)

        # -------------------------
        # Simple types
        # -------------------------
        if origin is None:
            if typ is type(None):
                return "NoneType"
            return TypeRegistry._types.get(typ.__name__, typ).__name__

        # -------------------------
        # Generics (list, dict, etc.)
        # -------------------------
        inner = ", ".join(self._type_name(a) for a in args)
        return f"{origin.__name__}[{inner}]"

    def _resolve_key(self, key: str) -> str:
        """
        Resolve alias → canonical key.
        """
        if key in self._aliases:
            return self._aliases[key]

        raise KeyError(f'"{key}" does not exist in section {self.name}')

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

            keys = [k.strip() for k in key_part.split("|")]
            main_key = keys[0]
            type_str = type_part.strip()
            value_str = value_str.strip()

            typ = parse_type(type_str)
            value = TypeRegistry.deserialize(value_str, typ)

            section._items[main_key] = (typ, value)

            for alias in keys:
                section._aliases[alias] = main_key

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

        path.write_text("# Rheel Data Management 2.5\n\n" + "\n".join(lines).rstrip(), "utf-8")

    @classmethod
    def load(cls, filename: str | Path, default: dict | Obj | bool | None = None) -> Obj | bool:
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
            if isinstance(default, bool):
                return copy.deepcopy(default)
            if isinstance(default, cls):
                return copy.deepcopy(default)
            if isinstance(default, TempObj):
                raise TypeError("Default cannot be TempObj for Obj.load()")
            if isinstance(default, dict):
                return cls.from_dict(default)
            return cls()

        content = path.read_text("utf-8").splitlines()

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
    def from_dict(cls, data: dict, default_section = "not sectioned") -> Obj:
        """
        Create Obj from a dictionary.

        Rules:
            - Top-level dict values become sections
            - Top-level non-dict values go into `default_section`
            - Values may be:
                (type, value) tuples
                or plain values (type inferred)
        """
        obj = cls()

        if not isinstance(data, dict):
            raise TypeError("Input data must be a dictionary")

        for key, value in data.items():

            # -------- Case 1: Proper section --------
            if isinstance(value, dict):
                section = obj.section(key)

                for subkey, entry in value.items():

                    # (type, value)
                    if (
                        isinstance(entry, tuple)
                        and len(entry) == 2
                        and isinstance(entry[0], type)
                    ):
                        typ, val = entry
                    else:
                        typ = type(entry)
                        val = entry

                    section.set(subkey, typ, val)

            # -------- Case 2: Top-level value --------
            else:
                section = obj.section(default_section)

                if (
                    isinstance(value, tuple)
                    and len(value) == 2
                    and isinstance(value[0], type)
                ):
                    typ, val = value
                else:
                    typ = type(value)
                    val = value

                section.set(key, typ, val)

        return obj

    @classmethod
    def convert_file(cls, filename: str | Path, default_section = "not sectioned", overwrite = False) -> Obj:
        """
        Convert JSON, TOML, YAML, or INI into .rdm format.

        If overwrite=True, deletes original file after conversion.
        """

        path = Path(filename)

        if not path.exists():
            raise FileNotFoundError(path)

        suffix = path.suffix.lower()

        # -------- Load Data --------

        if suffix == ".json":
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

        elif suffix == ".toml":
            if tomllib:
                with open(path, "rb", encoding="utf-8") as f:
                    data = tomllib.load(f)
            elif toml:
                with open(path, "r", encoding="utf-8") as f:
                    data = toml.load(f)
            else:
                raise RuntimeError("TOML requires Python 3.11+ or 'toml' package.")

        elif suffix in (".yaml", ".yml"):
            if not yaml:
                raise RuntimeError("YAML support requires PyYAML.")
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

        elif suffix == ".ini":
            parser = configparser.ConfigParser()
            parser.read(path)

            data = {}

            # Sections
            for section in parser.sections():
                data[section] = dict(parser[section])

            # Handle DEFAULT section
            if parser.defaults():
                data["default"] = dict(parser.defaults())

        else:
            raise ValueError(f"Unsupported file type: {suffix}")

        if not isinstance(data, dict):
            raise TypeError("Top-level structure must be a dictionary")

        # -------- Convert --------

        obj = cls.from_dict(data, default_section)

        new_path = path.with_suffix(".rdm")
        obj.save(new_path)

        if overwrite:
            path.unlink()

        return obj

class TempObj(Obj):
    """
    Temporary Rheel Data (.rtd)

    Sections represent expiration timestamps (UTC ISO format).
    Keys are globally unique across all expiration sections.
    Expired sections are automatically removed on save().
    """

    # =========================================================
    # Internal Utilities
    # =========================================================

    @staticmethod
    def _ensure_utc(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            raise ValueError("Expiration datetime must be timezone-aware.")
        return dt.astimezone(timezone.utc)

    def _parse_section_time(self, section_name: str) -> datetime:
        return datetime.fromisoformat(section_name)

    def _remove_key_globally(self, key: str):
        """Ensure keys are globally unique across expiration sections."""
        for section in list(self._sections.values()):
            if key in section._items:
                section.delete(key)

    def _cleanup_expired(self) -> bool:
        """
        Remove expired sections permanently.
        Used only when saving.
        """
        now = datetime.now(timezone.utc)
        removed = False

        for name in list(self._sections.keys()):
            expire_time = self._parse_section_time(name)

            if expire_time <= now:
                del self._sections[name]
                removed = True

        return removed

    # =========================================================
    # Public API
    # =========================================================

    def set(
        self,
        key: str,
        typ: type,
        value: Any,
        *,
        ttl: int | float | timedelta | None = None,
        expires_at: datetime | None = None
    ):
        """
        Set a temporary key.

        Exactly one of `ttl` or `expires_at` must be provided.

        - ttl: seconds or timedelta
        - expires_at: timezone-aware datetime (UTC will be enforced)
        """

        if (ttl is None) == (expires_at is None):
            raise ValueError("Provide exactly one of ttl or expires_at.")

        if ttl is not None:
            if isinstance(ttl, timedelta):
                expire_time = datetime.now(timezone.utc) + ttl
            else:
                expire_time = datetime.now(timezone.utc) + timedelta(seconds=ttl)
        else:
            expire_time = self._ensure_utc(expires_at)

        expire_time = self._ensure_utc(expire_time)

        # Enforce global uniqueness
        self._remove_key_globally(key)

        section_name = expire_time.isoformat()
        section = self.section(section_name)
        section.set(key, typ, value)

    def get(self, key: str, default: Any = KeyError) -> Any | ExpiredKey:
        """
        Retrieve key across expiration sections.

        Returns:
            - Value if valid
            - ExpiredKey if expired (and not cleaned up, else )
            - default if not found
        """
        now = datetime.now(timezone.utc)

        for section_name, section in self._sections.items():
            if key in section._items:
                expire_time = self._parse_section_time(section_name)

                if expire_time <= now:
                    return ExpiredKey(key, expire_time)

                return section.get(key)
        if default is KeyError: raise KeyError(f"\"{key}\" does not exist")
        else:                   return default

    def delete(self, key: str):
        """
        Delete a key globally from RTD.

        Removes the key from its expiration section.
        Removes the section if it becomes empty.
        """
        for section_name, section in list(self._sections.items()):
            if key in section._items:
                section.delete(key)

                # Remove empty expiration section
                if not section._items:
                    del self._sections[section_name]

                return
        raise KeyError(f"\"{key}\" does not exist in RTD.")

    def add(self, key: str, value: Any):
        """
        Add or subtract numeric or datetime values.

        Delegates to underlying Section.add().
        Raises ExpiredKey if expired.
        """
        now = datetime.now(timezone.utc)

        for section_name, section in self._sections.items():
            if key in section._items:
                expire_time = self._parse_section_time(section_name)

                if expire_time <= now:
                    raise ExpiredKey(key, expire_time)

                section.add(key, value)
                return
        raise KeyError(f"\"{key}\" does not exist in RTD.")

    def multiply(self, key: str, factor: int | float):
        """
        Multiply numeric values.

        Delegates to underlying Section.multiply().
        Raises ExpiredKey if expired.
        """
        now = datetime.now(timezone.utc)

        for section_name, section in self._sections.items():
            if key in section._items:
                expire_time = self._parse_section_time(section_name)

                if expire_time <= now:
                    raise ExpiredKey(key, expire_time)

                section.multiply(key, factor)
                return
        raise KeyError(f"\"{key}\" does not exist in RTD.")

    def extend(self, key: str, value: Any):
        """
        Dynamically extend value based on type.

        Delegates to underlying Section.extend().
        Raises ExpiredKey if expired.
        """
        now = datetime.now(timezone.utc)

        for section_name, section in self._sections.items():
            if key in section._items:
                expire_time = self._parse_section_time(section_name)

                if expire_time <= now:
                    raise ExpiredKey(key, expire_time)

                section.extend(key, value)
                return
        raise KeyError(f"\"{key}\" does not exist in RTD.")

    def get_expiration(self, key: str) -> datetime | None:
        now = datetime.now(timezone.utc)

        for section_name, section in self._sections.items():
            if key in section._items:
                expire_time = self._parse_section_time(section_name)

                if expire_time <= now:
                    return None  # already expired

                return expire_time

        return None

    def extend_expiration(
        self,
        key: str,
        *,
        seconds: int | float | None = None,
        delta: timedelta | None = None,
        new_expires_at: datetime | None = None
    ):
        """
        Extend or change expiration of a key.

        Provide exactly one of:
            - seconds
            - delta
            - new_expires_at
        """
        if sum(x is not None for x in (seconds, delta, new_expires_at)) != 1:
            raise ValueError("Provide exactly one extension method.")

        # Find key
        for section_name, section in list(self._sections.items()):
            if key in section._items:
                typ, value = section._items[key]

                old_expire = self._parse_section_time(section_name)

                if seconds is not None:
                    new_expire = old_expire + timedelta(seconds=seconds)
                elif delta is not None:
                    new_expire = old_expire + delta
                else:
                    new_expire = self._ensure_utc(new_expires_at)

                new_expire = self._ensure_utc(new_expire)

                # Remove from old section
                section.delete(key)

                # Remove empty section
                if not section._items:
                    del self._sections[section_name]

                # Reinsert with new expiration
                new_section = self.section(new_expire.isoformat())
                new_section.set(key, typ, value)

                return

        raise KeyError(f"{key} does not exist in RTD.")

    def save(self, filename: str | Path):
        """
        Save RTD file sorted by expiration (soonest first).
        Deletes expired sections permanently.
        Deletes file if empty.
        """
        self._cleanup_expired()
        path = Path(filename)
        if path.suffix != ".rtd":
            path = path.with_suffix(".rtd")

        # Delete file if no sections
        if not self._sections:
            path.unlink(missing_ok=True)
            return

        sorted_sections = sorted(
            self._sections.values(),
            key=lambda sec: self._parse_section_time(sec.name)
        )

        lines = []
        for section in sorted_sections:
            lines.extend(section.serialize())
            lines.append("")

        path.write_text("# Rheel Temporary Data @ Rheel Data Management 2.5\n\n" + "\n".join(lines).rstrip(), "utf-8")

    @classmethod
    def load(cls, filename: str | Path, default: TempObj | bool | None = None) -> TempObj:
        """
        Load RTD file.

        Parameters:
            default:
                - TempObj → returned (deep copy) if file missing or empty
                - True    → return empty TempObj
                - False   → raise FileNotFoundError
                - None    → return empty TempObj (default behavior)
        """
        path = Path(filename)
        if path.suffix != ".rtd":
            path = path.with_suffix(".rtd")

        # ---------------------------------------------------------
        # File does not exist
        # ---------------------------------------------------------
        if not path.exists():
            if isinstance(default, bool):
                return copy.deepcopy(default)
            if isinstance(default, Obj):
                raise TypeError("Default cannot be Obj for TempObj.load()")
            if isinstance(default, cls):
                return copy.deepcopy(default)
            if isinstance(default, dict):
                return cls.from_dict(default)
            return cls()

        # ---------------------------------------------------------
        # Parse file
        # ---------------------------------------------------------
        content = path.read_text("utf-8").splitlines()
        temp = cls()

        current_name = None
        buffer = []

        for raw_line in content:
            stripped = raw_line.strip()

            if not stripped or stripped.startswith("#"):
                continue

            if stripped.startswith("[") and stripped.endswith("]"):
                if current_name:
                    temp._sections[current_name] = Section.from_lines(current_name, buffer)
                    buffer = []
                current_name = stripped[1:-1]
            else:
                buffer.append(raw_line)

        if current_name:
            temp._sections[current_name] = Section.from_lines(current_name, buffer)

        # ---------------------------------------------------------
        # Empty file after parsing
        # ---------------------------------------------------------
        if not temp._sections:
            path.unlink(missing_ok=True)

            if isinstance(default, cls):
                return copy.deepcopy(default)
            return cls()
        return temp