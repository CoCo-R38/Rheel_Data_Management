# Rheel Data Management

Strictly-typed, human-readable data management for Python.

Rheel Data Management (RDM) provides a clean `.rdm` file format and
Python API for structured, section-based data storage with enforced
types.

It is designed for developers who want more structure and type safety
than JSON or TOML --- without the complexity of a database.

------------------------------------------------------------------------

## ✨ Features

-   ✅ Strict type enforcement
-   ✅ Native Python type support
-   ✅ Nested generics (`list[int]`, `dict[int, str]`)
-   ✅ Union types (`str | int`)
-   ✅ Mixed generics (`list[str | int]`)
-   ✅ Section-based structure
-   ✅ Human-readable format
-   ✅ Atomic file saves (corruption protection)
-   ✅ Custom type registry
-   ✅ Supports `datetime`, `date`, `time`, and `pathlib.Path`

------------------------------------------------------------------------

## 📦 Installation

``` bash
pip install Rheel-Data-Management
```

------------------------------------------------------------------------

## 📥 Import

``` python
import rheelDM
```

------------------------------------------------------------------------

## 📄 Example `.rdm` File

``` rdm
[user123]
name  : str           = "CoCo"
score : int           = 42
tags  : list[str]     = ["admin", "tester"]
prefs : dict[int,str] = {1: "dark", 2: "light"}
```

Clean. Typed. Readable.

------------------------------------------------------------------------

## 🚀 Basic Usage

### Create and Save

``` python
import rheelDM

data = rheelDM.Obj()

user = data.section("user123")
user.set("name", str, "CoCo")
user.set("score", int, 42)
user.set("tags", list[str], ["admin", "tester"])
user.set("prefs", dict[int, str], {1: "dark", 2: "light"})

data.save("botdata.rdm")
```

------------------------------------------------------------------------

### Load Data

``` python
loaded = rheelDM.Obj.load("botdata.rdm")

user = loaded.section("user123")

print(user.get("name"))   # "CoCo"
print(user.get("score"))  # 42
```

------------------------------------------------------------------------

## 🧠 Supported Types

### Native Python Types

-   `str`
-   `int`
-   `float`
-   `bool`
-   `list[T]`
-   `set[T]`
-   `tuple[T]`
-   `dict[K, V]`
-   Nested generics (e.g. `list[dict[int, str]]`)
-   Union types (`str | int`)
-   Mixed generics (`list[str | int]`)

------------------------------------------------------------------------

### Date & Path Types

-   `datetime`
-   `date`
-   `time`
-   `Path`

Example:

``` python
from datetime import datetime
from pathlib import Path

data.section("user").set("last_login", datetime, datetime.now())
data.section("user").set("config_path", Path, Path("config/settings.txt"))
```

------------------------------------------------------------------------

## 🧩 Custom Type Registry

You can register your own types globally.

``` python
import rheelDM

class Color:
    def __init__(self, hex_code: str):
        self.hex = hex_code

rheelDM.TypeRegistry.register(
    "Color",
    Color,
    lambda v: f'"{v.hex}"',
    lambda v: Color(v.strip('"'))
)
```

Now you can use it like any native type:

``` python
data.section("settings").set("theme", Color, Color("#ff8800"))
```

------------------------------------------------------------------------

## 🛡 Why RDM Instead of JSON?

### Strict Typing

JSON does not enforce types.\
RDM validates everything on write and load.

### Python-Native Types

JSON cannot store: - `datetime` - `Path` - `set` - `tuple` - Union types - Nested generics

RDM can.

### Cleaner Structure

Section-based format keeps large files organized and readable.

### Human Editable

Minimal syntax:

    key : type = value

------------------------------------------------------------------------

## 🎯 Ideal Use Cases

-   Game save systems
-   Discord bot data
-   Typed configuration systems
-   CLI tool configs
-   Small to medium persistent data storage
