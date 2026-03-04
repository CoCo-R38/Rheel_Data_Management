# Rheel Data Management

![Python](https://img.shields.io/badge/python-3.9+-blue.svg)
![License](https://img.shields.io/badge/license-GPL_3.0-green.svg)

Strictly-typed, human-readable data management for Python.

Rheel Data Management (RDM) provides a clean `.rdm` file format and
Python API for structured, section-based data storage with enforced
types.

Since version 2.0 RDM features Rheel Temporary Data (RTD), which
provides clean `.rtd` files for storing temporary data that expires
at a given time. RTD is not section-based but features all other
functions that RDM does.

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

**NEW in v2:**
- Temporary data system with expiration support (.rtd)
- Per-key TTL (time-to-live) expiration
- Automatic expired key cleanup on save
- Expiration extension and inspection API

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
# Rheel Data Management 2.0

[user123]
name  : str           = "Steve"
score : int           = 42
tags  : list[str]     = ["admin", "tester"]
prefs : dict[int,str] = {1: "dark", 2: "light"}
```

## 📄 Example `.rtd` File
``` rtd
# Rheel Temporary Data @ Rheel Data Management 2.0

[2026-03-04T18:14:37.891803+00:00]
effect : str = "burning"

[2026-03-04T18:35:07.172342+00:00]
premium_member : bool = True
```

Clean. Typed. Readable.

------------------------------------------------------------------------

## 🚀 Basic Usage

For each heading there are 2 examples (when required). The first is RDM and the second is RTD

### Create and Save

``` python
import rheelDM

data = rheelDM.Obj()
user = data.section("user123") # for simplicity user always refers to this section in RDM files

user.set("name", str, "Steve")
user.set("score", int, 42)
user.set("tags", list[str], ["admin", "tester"])
user.set("prefs", dict[int, str], {1: "dark", 2: "light"})

data.save("botdata.rdm")
```
``` python
import rheelDM, datetime

temp = rheelDM.TempObj()

temp.set("name", str, "Steve", ttl=30) # Expires 30 seconds from now (also works with datetime.timedelta)
temp.set("score", int, 42, expires_at=datetime.datetime(2026,3,3,18,0,tzinfo=datetime.timezone.utc)) # Expires at given timestamp

temp.save("tempbotdata.rtd")
```

### Load Data

``` python
from datetime import datetime

default_data = rheelDM.Obj()
default_data.section("user123").set("name", str, "noName")
default_data.section("user123").set("score", int, 0)

default_items = rheelDM.Obj.load("default_items.rdm")

loaded = rheelDM.Obj.load("botdata.rdm", default_data) # uses a copy of default if file not found (this can also be a boolean for catching missing files)
user = loaded.section("user123")

print(user.get("name"))  # "Steve"
print(user.get("score")) # 42
print(user.get("items", default_items)) # [1] (uses a copy of default because "items" is not defined in botdata.rdm)
```
``` python
default = rheel.TempObj.load("default.rtd")

loaded = rheel.TempObj.load("tempbotdata.rtd", default)

print(loaded.get("score")) # 42 or <ExpiredKey key="score" expired_at='2026-03-03T18:00:00.000000+00:00'>
print(loaded.get("name", default)) # "Steve" or default
print(loaded.get_expiration("name")) # timestamp of expiration
```

### Modify Data

#### Overwrite
```python
# same with RTD
user.set("name", str, "Alex")
print(user.get("name")) # "Alex"

# How to prevent overwrites:
user.set("name", str, "Steve", overwrite=False) # -> raise KeyError
print(user.get("name"))                         # "Alex"
```
#### Add or Multiply (`int`, `float`, `datetime`)
```python
# same with RTD
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
# same with RTD
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
#### Extend Expiration:
```python
# not featured in RDM
temp.extend_expiration("name", seconds=30)                                                                   # adds 30 seconds
temp.extend_expiration("name", new_expires_at=datetime.datetime(2026,3,3,18,0,tzinfo=datetime.timezone.utc)) # set new expiration timestamp
```
#### Convert non-RDM Files
```python
# not featured in RTD
rheelDM.Obj.convert_file("/settings/data.json", overwrite=True)
rheelDM.Obj.load("/settings/data.rdm")
```

### Delete Data
```python
user.delete("score") # key, value and type of "score" will be deleted entirely from the RDM or RTD file.
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
# same with TempObj and set()
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

Section-based (not RTD) and auto-aligned format keeps large files organized and readable.

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