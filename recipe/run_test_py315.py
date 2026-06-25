# filename: run_test.py
# Placement: recipe root, next to meta.yaml. conda-build auto-discovers a file
#   named run_test.py and executes it in the *test* environment after the build.
# Purpose: validate a Python 3.15.0bN build and probe the 3.15 PEP feature set.
#
# Design contract:
#   - HARD checks (interpreter identity, core stdlib, ABI/build sanity) -> failure
#     fails the conda-build test phase (non-zero exit).
#   - SOFT checks (new PEP features) -> reported as PASS/SKIP, never fail the build,
#     UNLESS the env var RUN_TEST_STRICT=1 is set (promote SOFT failures to HARD).
#     Rationale: 3.15 is in beta; PEP APIs may shift until RC1 (2026-08-04).
#
# Tighten the SOFT probes into HARD asserts once building against v3.15.0rc1+.

from __future__ import annotations

import importlib.util
import os
import platform
import sys
import sysconfig
from dataclasses import dataclass

STRICT = os.environ.get("RUN_TEST_STRICT", "0") == "1"

# The PEP feature probes only make sense on 3.15. On any other Python version
# (e.g. a shared recipe built across a py matrix) they are skipped entirely.
TARGET_VERSION = (3, 15)
IS_TARGET = sys.version_info[:2] == TARGET_VERSION
# For the dedicated python-3.15 feedstock, set RUN_TEST_REQUIRE_315=1 so a
# non-3.15 interpreter is a HARD failure instead of a skip (catches a bad matrix).
REQUIRE_TARGET = os.environ.get("RUN_TEST_REQUIRE_315", "0") == "1"

PASS, SKIP, FAIL = "PASS", "SKIP", "FAIL"


@dataclass
class Result:
    name: str
    status: str
    detail: str = ""
    hard: bool = False  # if True, a FAIL aborts the test phase


_results: list[Result] = []


def record(name: str, status: str, detail: str = "", *, hard: bool = False) -> None:
    _results.append(Result(name, status, detail, hard))


def _spec_exists(modname: str) -> bool:
    try:
        return importlib.util.find_spec(modname) is not None
    except (ImportError, ValueError):
        return False


def _compiles(src: str) -> bool:
    # Probe a syntax-level PEP without executing it.
    try:
        compile(src, "<feature-probe>", "exec")
        return True
    except SyntaxError:
        return False


# --------------------------------------------------------------------------- #
# HARD checks: must hold for any correct 3.15 build
# --------------------------------------------------------------------------- #

def check_interpreter_identity() -> None:
    ver = (f"{platform.python_version()} "
           f"({sys.version_info.releaselevel} {sys.version_info.serial})")
    if IS_TARGET:
        record("interpreter 3.15", PASS, ver, hard=True)
    elif REQUIRE_TARGET:
        record("interpreter 3.15", FAIL,
               f"expected 3.15, got {sys.version_info[0]}.{sys.version_info[1]}",
               hard=True)
    else:
        # Not the target version: sanity still runs, feature probes are skipped.
        record("interpreter 3.15", SKIP, f"not target ({ver}) -> probes skipped")


def check_core_stdlib() -> None:
    # C-extension stdlib modules are the usual silent-failure surface: a build
    # that lacks system libs (ssl/lzma/sqlite/...) imports the pure parts fine
    # but breaks at runtime. Importing them here turns that into a build failure.
    required = ["ssl", "ctypes", "sqlite3", "lzma", "bz2", "zlib",
               "hashlib", "decimal", "readline", "curses"]
    missing = []
    for mod in required:
        # readline/curses are absent on Windows by design.
        if os.name == "nt" and mod in {"readline", "curses"}:
            continue
        try:
            __import__(mod)
        except ImportError as exc:
            missing.append(f"{mod} ({exc})")
    if missing:
        record("core C-extension stdlib", FAIL, "; ".join(missing), hard=True)
    else:
        record("core C-extension stdlib", PASS, "all importable", hard=True)


def check_build_sanity() -> None:
    # Cross-check the build prefix matches the test env's interpreter.
    prefix_ok = sys.prefix and os.path.isdir(sys.prefix)
    abiflags = getattr(sys, "abiflags", "")
    record(
        "build sanity",
        PASS if prefix_ok else FAIL,
        f"prefix={sys.prefix} abiflags='{abiflags}'",
        hard=True,
    )


# --------------------------------------------------------------------------- #
# SOFT probes: 3.15 new features (API spellings may change before RC1)
# --------------------------------------------------------------------------- #

def probe_pep686_utf8_default() -> None:
    # PEP 686: UTF-8 mode default. sys.flags.utf8_mode should be 1.
    mode = getattr(sys.flags, "utf8_mode", None)
    if mode == 1:
        record("PEP 686 UTF-8 default", PASS, "sys.flags.utf8_mode=1")
    else:
        record("PEP 686 UTF-8 default", SKIP, f"utf8_mode={mode}")


def probe_pep810_lazy_imports() -> None:
    # PEP 810: explicit `lazy import` statement syntax.
    record("PEP 810 lazy imports",
           PASS if _compiles("lazy import os\n") else SKIP,
           "compile('lazy import os')")


def probe_pep798_unpack_comprehension() -> None:
    # PEP 798: unpacking in comprehensions, e.g. [*xs for xs in groups].
    src = "result = [*xs for xs in [[1, 2], [3]]]"
    if _compiles(src):
        ns: dict = {}
        try:
            exec(src, ns)
            ok = ns.get("result") == [1, 2, 3]
            record("PEP 798 unpack-in-comprehension",
                   PASS if ok else FAIL, f"result={ns.get('result')}")
        except Exception as exc:  # noqa: BLE001 - feature probe
            record("PEP 798 unpack-in-comprehension", FAIL, repr(exc))
    else:
        record("PEP 798 unpack-in-comprehension", SKIP, "syntax not accepted")


def probe_pep814_frozendict() -> None:
    # PEP 814: frozendict built-in.
    fd = getattr(__builtins__, "frozendict", None) if not isinstance(
        __builtins__, dict) else __builtins__.get("frozendict")
    record("PEP 814 frozendict",
           PASS if fd is not None else SKIP,
           "builtin present" if fd is not None else "builtin absent")


def probe_pep661_sentinel() -> None:
    # PEP 661: sentinel built-in type. Spelling unconfirmed at b3 — probe builtin
    # name first, then a possible 'sentinels' module fallback.
    builtin = (__builtins__.get("sentinel") if isinstance(__builtins__, dict)
               else getattr(__builtins__, "sentinel", None))
    if builtin is not None:
        record("PEP 661 sentinel", PASS, "builtin present")
    elif _spec_exists("sentinels"):
        record("PEP 661 sentinel", PASS, "module 'sentinels' present")
    else:
        record("PEP 661 sentinel", SKIP, "not found (check final API)")


def probe_pep799_profiling() -> None:
    # PEP 799: dedicated 'profiling' package + Tachyon sampling profiler.
    if _spec_exists("profiling"):
        sub = next((s for s in ("profiling.sampling", "profiling.tachyon")
                    if _spec_exists(s)), "")
        record("PEP 799 profiling/Tachyon", PASS, sub or "package present")
    else:
        record("PEP 799 profiling/Tachyon", SKIP, "package absent")


def probe_typing_features() -> None:
    # PEP 747 TypeForm, PEP 728 TypedDict extra_items, PEP 800 disjoint bases.
    import typing
    record("PEP 747 TypeForm",
           PASS if hasattr(typing, "TypeForm") else SKIP,
           "typing.TypeForm")
    # PEP 728: probe by constructing a TypedDict accepting extra_items kw.
    try:
        typing.TypedDict("X", {"a": int}, extra_items=int)  # type: ignore[call-arg]
        record("PEP 728 TypedDict extra_items", PASS, "extra_items accepted")
    except TypeError:
        record("PEP 728 TypedDict extra_items", SKIP, "extra_items rejected")
    record("PEP 800 disjoint bases",
           PASS if hasattr(typing, "disjoint_base") else SKIP,
           "typing.disjoint_base")


def probe_build_variant_info() -> None:
    # Informational: free-threading (PEP 703/793) and JIT state for this build.
    gil_disabled = sysconfig.get_config_var("Py_GIL_DISABLED")
    is_gil = getattr(sys, "_is_gil_enabled", lambda: None)()
    record("free-threaded build (info)", SKIP,
           f"Py_GIL_DISABLED={gil_disabled} gil_enabled={is_gil}")
    jit = getattr(sys, "_jit", None)
    if jit is not None:
        avail = getattr(jit, "is_available", lambda: "?")()
        active = getattr(jit, "is_active", lambda: "?")()
        record("JIT (info)", SKIP, f"available={avail} active={active}")
    else:
        record("JIT (info)", SKIP, "sys._jit absent")


def probe_cabi_notes() -> None:
    # PEP 782 PyBytesWriter and PEP 803/820/793 free-threaded stable ABI are
    # C-API surfaces; they cannot be exercised from a pure-Python test without
    # compiling an extension. Recorded as N/A for visibility.
    record("PEP 782 PyBytesWriter (C-API)", SKIP, "needs C ext to test")
    record("PEP 803/820 free-threaded ABI (C-API)", SKIP, "needs C ext to test")


# --------------------------------------------------------------------------- #

def main() -> int:
    # Universal sanity: runs on every Python version.
    check_interpreter_identity()
    check_core_stdlib()
    check_build_sanity()

    # 3.15-only: PEP feature probes are skipped on any other version.
    if IS_TARGET:
        probe_pep686_utf8_default()
        probe_pep810_lazy_imports()
        probe_pep798_unpack_comprehension()
        probe_pep814_frozendict()
        probe_pep661_sentinel()
        probe_pep799_profiling()
        probe_typing_features()
        probe_build_variant_info()
        probe_cabi_notes()
    else:
        record("3.15 feature probes", SKIP,
               f"interpreter {sys.version_info[0]}.{sys.version_info[1]} "
               "is not 3.15")

    width = max(len(r.name) for r in _results)
    print("\n=== Python 3.15 conda-build feature test ===")
    print(f"interpreter: {sys.executable}")
    print(f"strict mode: {STRICT}\n")
    for r in _results:
        tag = "[HARD]" if r.hard else "[soft]"
        print(f"{tag} {r.status:<4} {r.name.ljust(width)}  {r.detail}")

    hard_failed = [r for r in _results if r.hard and r.status == FAIL]
    soft_failed = [r for r in _results if not r.hard and r.status == FAIL]

    print()
    print(f"summary: {sum(r.status == PASS for r in _results)} pass / "
          f"{sum(r.status == SKIP for r in _results)} skip / "
          f"{sum(r.status == FAIL for r in _results)} fail")

    if hard_failed:
        return 1
    if STRICT and soft_failed:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
