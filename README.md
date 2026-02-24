# Rheel Data Management

![Python](https://img.shields.io/badge/python-3.13+-blue.svg)
![License](https://img.shields.io/badge/license-GPL_3.0-green.svg)

Strictly-typed, human-readable data management for Python.

Rheel Data Management (RDM) provides a clean `.rdm` file format and
Python API for structured, section-based data storage with enforced
types.

It is designed for developers who want more structure and type safety
than JSON or TOML --- without the complexity of a database.

------------------------------------------------------------------------

## ✨ Features

- Strict type enforcement
- Native Python type support
- Nested generics (`list[int]`, `dict[int, str]`)
- Union types (`str | int`)
- Mixed generics (`list[str | int]`)
- Dynamic operations (`add()`, `extend()`, `multiply()`)
- Key deletion support (`delete()`)
- Section-based structure
- Human-readable aligned format
- Atomic file saves (corruption protection)
- Custom type registry
- Supports `datetime`, `date`, `time`, and `Path` natively
- Safe variable handling with deep copy

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
name  : str           = "Steve"
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
user = data.section("user123") # for simplicity user always refers to this section

user.set("name", str, "Steve")
user.set("score", int, 42)
user.set("tags", list[str], ["admin", "tester"])
user.set("prefs", dict[int, str], {1: "dark", 2: "light"})

data.save("botdata.rdm")
```

### Load Data

``` python
from datetime import datetime

default_data = rheelDM.Obj()
default_data.section("user123").set("name", str, "noName")
default_data.section("user123").set("score", int, 0)

default_items = rheelDM.Obj()
default_items.section("user123").set("items", list, [1])

loaded = rheelDM.Obj.load("botdata.rdm", default_data) # uses a copy of default if file not found
user = loaded.section("user123")

print(user.get("name"))  # "Steve"
print(user.get("score")) # 42
print(user.get("items", default_items)) # [1] (uses a copy of default because "items" is not defined in botdata.rdm)
```

### Modify Data

#### Overwrite
```python
user.set("name", str, "Alex")
print(user.get("name")) # "Alex"

# How to prevent overwrites:
user.set("name", str, "Steve", overwrite=False) # -> raise KeyError
print(user.get("name"))                         # "Alex"
```
#### Add or Multiply (`int`, `float`, `datetime`)
```python
from datetime import datetime

user.set("score", int, 10)   # 10
user.add("score", 5)         # 15
user.add("score", -3)        # 12
user.multiply("score", 2)    # 24
user.multiply("score", 0.25) # 6

user.set("last_login", datetime, datetime.now()) # 2026-02-21T21:39:18.398038
user.add("last_login", 3605)                     # 2026-02-21T22:39:23.398038
```
#### Extend (`str`, `list`, `set`, `dict`, `Path`)
```python
from pathlib import Path

user.set("name", str, "Steve")   # "Steve"
user.extend("name", " the Hero") # "Steve the Hero"

user.set("items", list[int], [1]) # [1]
user.extend("items", 2)           # [1, 2]
user.extend("items", [3, 4])      # [1, 2, 3, 4]

user.set("tags", set[str], {"a"}) # {"a"}
user.extend("tags", "b")          # {"a", "b"}

user.set("settings", dict[str,int], {"a":1}) # {"a": 1}
user.extend("settings", {"b":2})             # {"a": 1, "b": 2}

config_dir = Path("/settings")
user.set("config_file", Path, config_dir)   # Path(/settings)
user.extend("config_file", "steve3828.rdm") # Path(/settings/steve3828.rdm)
```

### Delete Data
```python
user.delete("score") # key, value and type of "score" will be deleted entirely from the RDM file.
```

------------------------------------------------------------------------

## 🧠 Supported Types

-   `str`
-   `int`
-   `float`
-   `bool`
-   `None`
-   `list[T]`
-   `set[T]`
-   `tuple[T]`
-   `dict[K, V]`
-   Nested generics (e.g. `list[dict[int, str]]`)
-   Union types (e.g. `str | int`)
-   Mixed generics (e.g. `list[str | int]`)
-   datetime:
    -   `datetime`
    -   `date`
    -   `time`
-   pathlib:
    -   `Path`

Example:

``` python
from datetime import datetime
from pathlib import Path

user.set("id", int, 1234567890)
user.set("names", dict[str, str], {"username": "steve3828", "displayname": "Steve"})
user.set("last_login", datetime, datetime.now())
user.set("config_file", Path, Path("config/settings.txt"))
```

------------------------------------------------------------------------

### Custom Type Registry

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

## 🛡 Why RDM Instead of JSON or TOML?

### Strict Typing

JSON and TOML do not enforce types.\
RDM validates everything on write and load.

### Python-Native Types

JSON cannot store:
- `datetime`
- `Path`
- `set`
- `tuple`
- Union types
- Nested generics
- `int` as `dict`-keys
- `None` (stores it as `null`)

TOML cannot store:
- `Path`
- `set`
- `None`
- `int` as `dict`-keys

RDM can store all of these, even the most complex and custom types.

### Cleaner Structure

Section-based and auto-aligned format keeps large files organized and readable.

### Human Editable

Minimal syntax makes manual edits easier than ever:

    key : type = value

------------------------------------------------------------------------

## 🎯 Ideal Use Cases

-   Game save systems
-   Discord bot data
-   Typed configuration systems
-   CLI tool configs
-   Small to medium persistent data storage