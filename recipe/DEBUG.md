# Unix Py_DEBUG spike (PKG-2624)

Time-boxed technical spike stacked on python-feedstock#256. **Not pkgs/main.** Product ticket PKG-2624 is closed (no market).

## What this is (and is not)

| Build | What you get | What you do not get |
|-------|----------------|---------------------|
| **This graph** (`--with-pydebug`) | `Py_DEBUG`, `'d' in sys.abiflags`, `sys.gettotalrefcount()`, `libpython3.15d.so` / `libpython3.15td.so` | DWARF-complete unstripped objects (conda-build may strip `.symtab` / `.debug_info`) |
| **`python -X dev`** | Runtime development checks on a **release** interpreter | `d` ABI, refcount APIs, debug libpython |
| **Windows `PCbuild -d` / `python3XX_d.lib`** | MSVC debug CRT import libs | **Out of this spike.** CBC is `# [not win]`; win PBP tasks are empty/skip |

Do not confuse the three. This dest is Unix `--with-pydebug` only.

## Gate: keep debug off pkgs/main

PBP `upload_channels` is **graph-wide**. Do **not** zip `channel_targets` with `python_debug` (F94). The dummy `channel_targets = ('abc','def')` in `meta.yaml` exists so the linter expands and `'conda-forge' in channel_targets` is false — leave it.

| File | Debug spike (this PR) | Before pkgs/main / #256-style py315 |
|------|------------------------|--------------------------------------|
| `recipe/conda_build_config.yaml` | `build_type: debug # [not win]` only; `freethreading: yes/no` | Restore `release` (and drop `debug` unless dest is still a testing label) |
| `abs.yaml` | `upload_channels: [ad-testing/label/py315-debug]` | `#256` keeps `ad-testing/label/py315`. Never point debug variants at `main` |

Release 3.15 stays on **#256** → `ad-testing/label/py315`. This PR is a **second graph**.

## Pinning a debug interpreter

Build string contains `_debug_` plus the ABI tag:

```text
python 3.15.* *_debug_cp315     # GIL debug
python 3.15.* *_debug_cp315t    # free-threading debug
```

`run_exports` (when `build_type == debug`) already pins:

```text
python {{ ver2 }}.* *_debug_{{ abi_tag }}
```

Downstream recipes that must link the debug ABI should depend on that pin, **not** on a generic `python 3.15.*`.

Debug Python **cannot load release extensions** (and vice versa). `abiflags` `d` / `td` vs release `''` / `t` are different ABIs. Mixing them is a loader/ABI error, not a solver hint.

## Matrix

- `freethreading: yes/no` × `build_type: debug`
- **No `release` on this graph**
- GIL debug lib: `libpython3.15d.so` (`abiflags` contains `d`)
- FT debug lib: `libpython3.15td.so` (`abiflags` contains `td`; assert `'d' in sys.abiflags` covers both)
- Windows: **zero variants**. Do not add a win release variant onto `py315-debug`.

## Local conda-build

```bash
export ANACONDA_ROCKET_ENABLE_PY315=yes
cd /home/skupr/src/aggregate/python-feedstock
conda-build recipe --suppress-variables --error-overlinking --error-overdepending \
  -c defaults --override-channels
```

CBC is already debug-only on this branch, so omit `--variants`. Prefix:

```text
conda-bld/linux-64/python-3.15.0rc2-*_debug_cp315*.conda
```

On a tree that still has `release` (e.g. #256 HEAD) force one variant:

```bash
conda-build recipe --suppress-variables --error-overlinking --error-overdepending \
  -c defaults --override-channels \
  --variants "{'build_type': 'debug', 'freethreading': 'no'}"
```

`build_base.sh` already passes `--with-pydebug`, disables PGO/JIT on debug, and names `libpython${VERABI}`. Do not rewrite it unless a build proves a bug.

## ABI tests (CI)

Unconditional on this graph (`meta.yaml` `commands` + `run_test.py`). Do **not** rely on `PY_INTERP_DEBUG` — that is `script_env` (build), not the test env.

```bash
python -c "import sys; assert 'd' in sys.abiflags; assert hasattr(sys, 'gettotalrefcount'); print(sys.abiflags, sys.gettotalrefcount())"
```

Existing `libpython${VERABI}` tests already append `d` / `td`. Linux `libpython3.so` is gated `unix and build_type == "release"` (empty upstream for debug); leave it.

CMake `Python_FIND_ABI` already turns debug ON when `build_type == debug`.

## gdb / lldb / ELF (local only — not a PBP gate)

```bash
# GIL debug; FT: libpython3.15td.so
LIB=$PREFIX/lib/libpython3.15d.so
readelf -WS "$LIB"   # .dynsym required; .symtab / .debug_info may be stripped
readelf -d "$LIB"
nm -D "$LIB"

gdb -q "$PREFIX/bin/python" --batch -ex "set pagination off" \
  -ex "run -c 'import os; os.abort()'" -ex bt -ex quit
lldb -b -o "run -c 'import os; os.abort()'" -o bt -o quit "$PREFIX/bin/python"
```

If gdb backtraces are shallow, that is strip quality, not a missing `Py_DEBUG`. Do not expand this spike to unstrip unless it is a one-line recipe change. Use `/debug-elf` for RPATH/SONAME/arch, not for solver or graph triage.

## Out of scope

- Windows `PCbuild -d` / `python3XX_d.lib`
- numpy / pybind11 debug extension chain (later product)
- conda-forge `python_debug` `zip_keys` / real `channel_targets`
- pkgs/main, sanitizer/valgrind builds, paying-customer packaging
- Merging this PR (human-only; never pkgs/main)
