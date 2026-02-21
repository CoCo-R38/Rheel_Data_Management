# Rheel Data Management

This python project reinvents data management. This mildly-fast module protects and saves your data in .rdm files.

Why use this instead of json or toml?
It's (strictly) typed, human readable, section-based and you can edit it on the go (if you load and save it on every use).
It also has corruption-protection with atomic file rewrites.
It supports all native python types as well as datetime and pathlib.Path, but with the local custom type registry you can add as many types as you like (check source code for usage)!
