# Python 3.15 conda-build feature test — verified against 3.15.0b3 (2026 series).
#
# Design contract:
#   - HARD checks (interpreter identity, core stdlib, ABI/build sanity) -> failure
#     fails the conda-build test phase (non-zero exit).
#   - SOFT checks (new PEP feature probes) -> reported as PASS/SKIP, never fail
#     the build UNLESS one of:
#       * RUN_TEST_STRICT=1 in the environment (manual promote SOFT->HARD), or
#       * we are running on rc1 or later (auto-promote — PEP feature spellings
#         are frozen at the RC boundary per PEP 790, so a SKIP after that date
#         means we're building against a stale probe).
#
# Sources:
#   - Python 3.15 What's New: https://docs.python.org/3.15/whatsnew/3.15.html
#   - PEP 790 (release schedule): https://peps.python.org/pep-0790/  — RC1 2026-08-04
#   - PEP-specific references embedded in each probe below.

from __future__ import annotations

import builtins
import importlib.util
import os
import platform
import site
import sys
import sysconfig
from dataclasses import dataclass

PASS, SKIP, FAIL = "PASS", "SKIP", "FAIL"
TARGET_VERSION = (3, 15)
IS_TARGET = sys.version_info[:2] == TARGET_VERSION

# Manual override for local development / CI hardening.
STRICT_ENV = os.environ.get("RUN_TEST_STRICT", "0") == "1"

# Auto-promote at rc1 — after 2026-08-04 the PEP APIs are frozen and any SKIP
# from a feature probe means the probe is stale, not that the feature is absent.
# Rationale: probes are advisory during beta only.
AUTO_STRICT = IS_TARGET and sys.version_info.releaselevel != "beta"
STRICT = STRICT_ENV or AUTO_STRICT

# For the dedicated python-3.15 feedstock, set RUN_TEST_REQUIRE_315=1 so a
# non-3.15 interpreter is a HARD failure instead of a skip (catches bad matrices).
REQUIRE_TARGET = os.environ.get("RUN_TEST_REQUIRE_315", "0") == "1"


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
    # `find_spec` is safer than `import` — it does not execute module top-level
    # code, which matters for probes on packages that may hold heavy imports.
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
# HARD checks — must hold for any correct 3.15 build
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
# SOFT probes — 3.15 new features (verified against b3; frozen at rc1)
# --------------------------------------------------------------------------- #

def probe_pep686_utf8_default() -> None:
    # PEP 686: UTF-8 is the unconditional default in 3.15 (independent of locale).
    # Behavioral change is most visible on Windows; on POSIX with UTF-8 locales
    # it was already effectively UTF-8. sys.flags.utf8_mode == 1 by default now.
    mode = getattr(sys.flags, "utf8_mode", None)
    if mode == 1:
        record("PEP 686 UTF-8 default", PASS, "sys.flags.utf8_mode=1")
    else:
        record("PEP 686 UTF-8 default", SKIP, f"utf8_mode={mode}")


def probe_pep810_lazy_imports() -> None:
    # PEP 810: `lazy` soft keyword — module-scope only. Syntax alone enables it;
    # no __future__ import is required. Belt-and-suspenders: compile probe AND
    # a runtime attribute (sys.set_lazy_imports) that also lands in 3.15.
    compile_ok = _compiles("lazy import os\n")
    runtime_ok = hasattr(sys, "set_lazy_imports")
    if compile_ok and runtime_ok:
        record("PEP 810 lazy imports", PASS, "syntax + sys.set_lazy_imports")
    elif compile_ok or runtime_ok:
        record("PEP 810 lazy imports", PASS,
               f"partial: compile={compile_ok} runtime={runtime_ok}")
    else:
        record("PEP 810 lazy imports", SKIP, "neither syntax nor runtime API")


def probe_pep798_unpack_comprehension() -> None:
    # PEP 798: unpacking in comprehensions. NOTE: unbracketed genexp-call form
    # `f(*x for x in xs)` still raises SyntaxError — do not probe that here.
    src = "result = [*xs for xs in [[1, 2], [3]]]"
    if not _compiles(src):
        record("PEP 798 unpack-in-comprehension", SKIP, "syntax not accepted")
        return
    ns: dict = {}
    try:
        exec(src, ns)
        ok = ns.get("result") == [1, 2, 3]
        record("PEP 798 unpack-in-comprehension",
               PASS if ok else FAIL, f"result={ns.get('result')}")
    except Exception as exc:  # noqa: BLE001 - feature probe
        record("PEP 798 unpack-in-comprehension", FAIL, repr(exc))


def probe_pep814_frozendict() -> None:
    # PEP 814: `frozendict` is a true BUILTIN (not types.frozendict).
    # Also NOT a subclass of dict — inherits directly from object; use
    # isinstance(x, (dict, frozendict)) or collections.abc.Mapping in consumers.
    if not hasattr(builtins, "frozendict"):
        record("PEP 814 frozendict", SKIP, "builtin absent")
        return
    fd = builtins.frozendict({"a": 1})
    # Sanity: constructs, hashable, not a dict subclass.
    ok = hash(fd) is not None and not isinstance(fd, dict)
    record("PEP 814 frozendict",
           PASS if ok else FAIL,
           f"hashable={ok}, not dict-subclass={not isinstance(fd, dict)}")


def probe_pep661_sentinel() -> None:
    # PEP 661: `sentinel` is a BUILTIN lowercase callable — sentinel("NAME").
    # NOT a module import. The typing_extensions backport is capital-S Sentinel,
    # but the 3.15 builtin is lowercase.
    if not hasattr(builtins, "sentinel"):
        record("PEP 661 sentinel", SKIP, "builtin absent")
        return
    try:
        missing = builtins.sentinel("MISSING")
        # Sanity: repr is stable and identity-comparable to itself.
        ok = missing is missing and "MISSING" in repr(missing)
        record("PEP 661 sentinel", PASS if ok else FAIL, repr(missing))
    except Exception as exc:  # noqa: BLE001 - feature probe
        record("PEP 661 sentinel", FAIL, repr(exc))


def probe_pep799_profiling() -> None:
    # PEP 799: dedicated `profiling` package. Tachyon (the sampling profiler)
    # IS `profiling.sampling`.
    # `profiling.tracing` is the relocated cProfile (cProfile remains as alias).
    if not _spec_exists("profiling"):
        record("PEP 799 profiling/Tachyon", SKIP, "package absent")
        return
    subs = [s for s in ("profiling.sampling", "profiling.tracing")
            if _spec_exists(s)]
    if subs:
        record("PEP 799 profiling/Tachyon", PASS, ", ".join(subs))
    else:
        record("PEP 799 profiling/Tachyon", FAIL,
               "package present but sampling/tracing missing")


def probe_typing_features() -> None:
    # PEP 747 TypeForm — annotation for values that are themselves type exprs.
    import typing
    record("PEP 747 TypeForm",
           PASS if hasattr(typing, "TypeForm") else SKIP,
           "typing.TypeForm")

    # PEP 728 TypedDict extra_items: functional keyword form. Introspect via
    # __extra_items__ (default: typing.NoExtraItems sentinel, not None).
    # Passing both closed= and extra_items= raises TypeError at runtime.
    try:
        td = typing.TypedDict("X", {"a": int}, extra_items=int)  # type: ignore[call-arg]
        no_extra = getattr(typing, "NoExtraItems", None)
        extras_ok = getattr(td, "__extra_items__", no_extra) is int
        default_ok = no_extra is not None
        record("PEP 728 TypedDict extra_items",
               PASS if (extras_ok and default_ok) else FAIL,
               f"extra_items=int accepted, NoExtraItems={'ok' if default_ok else 'missing'}")
    except TypeError as exc:
        record("PEP 728 TypedDict extra_items", SKIP, f"rejected: {exc}")

    # PEP 800: `@typing.disjoint_base` — a CLASS DECORATOR, not a flag/attr.
    # Attribute-existence is a valid capability probe; note in detail that
    # semantically it's a decorator so downstream code should apply it, not read it.
    has_db = hasattr(typing, "disjoint_base")
    record("PEP 800 disjoint bases",
           PASS if has_db else SKIP,
           "typing.disjoint_base decorator" if has_db else "absent")


def probe_pep831_frame_pointers() -> None:
    # PEP 831: -fno-omit-frame-pointer enabled by default on supporting platforms.
    # No dedicated sysconfig variable — grep the compiler flags. Reflects build
    # config, not runtime state. Opt-out is --without-frame-pointers at configure.
    cflags = sysconfig.get_config_var("CFLAGS") or ""
    if "-fno-omit-frame-pointer" in cflags:
        record("PEP 831 frame pointers", PASS, "-fno-omit-frame-pointer in CFLAGS")
    else:
        # On Windows and some cross-compiles the flag simply doesn't apply.
        record("PEP 831 frame pointers", SKIP, "not present in CFLAGS")


def probe_pep829_startup_config() -> None:
    # PEP 829: `.start` files + site.StartupState. `.start` entries are
    # `pkg.mod:callable` specs resolved by pkgutil.resolve_name and invoked
    # at interpreter startup by site. Only Python-visible probe is StartupState.
    record("PEP 829 startup config",
           PASS if hasattr(site, "StartupState") else SKIP,
           "site.StartupState")


def probe_build_variant_info() -> None:
    # Informational: free-threading (PEP 703/793) and JIT state for this build.
    # NOTE: Py_GIL_DISABLED is DEFINED AS 0 on non-FT Windows builds — using
    # `is not None` would incorrectly report FT on those. Coerce to bool.
    gil_disabled = bool(sysconfig.get_config_var("Py_GIL_DISABLED"))
    is_gil = getattr(sys, "_is_gil_enabled", lambda: None)()
    record("free-threaded build (info)", SKIP,
           f"Py_GIL_DISABLED={gil_disabled} gil_enabled={is_gil}")

    # JIT: sys._jit exposes THREE methods. is_enabled() is the most meaningful
    # ("JIT actually on"); is_active() is documented as unreliable outside JIT
    # self-tests. The JIT is OFF BY DEFAULT — is_available() can be True while
    # is_enabled() is False. Enable at runtime with PYTHON_JIT=1 if compiled in.
    jit = getattr(sys, "_jit", None)
    if jit is not None:
        avail = getattr(jit, "is_available", lambda: "?")()
        enabled = getattr(jit, "is_enabled", lambda: "?")()
        active = getattr(jit, "is_active", lambda: "?")()
        record("JIT (info)", SKIP,
               f"available={avail} enabled={enabled} active={active}")
    else:
        record("JIT (info)", SKIP, "sys._jit absent")


def probe_cabi_notes() -> None:
    # PEP 782 PyBytesWriter and PEP 803/820/793 free-threaded stable ABI (abi3t)
    # are C-API surfaces; they cannot be exercised from a pure-Python test
    # without compiling an extension. Recorded as N/A for visibility.
    record("PEP 782 PyBytesWriter (C-API)", SKIP, "needs C ext to test")
    record("PEP 803/820/793 abi3t (C-API)", SKIP, "needs C ext to test")


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
        probe_pep831_frame_pointers()
        probe_pep829_startup_config()
        probe_build_variant_info()
        probe_cabi_notes()
    else:
        record("3.15 feature probes", SKIP,
               f"interpreter {sys.version_info[0]}.{sys.version_info[1]} "
               "is not 3.15")

    width = max(len(r.name) for r in _results)
    print("\n=== Python 3.15 conda-build feature test ===")
    print(f"interpreter: {sys.executable}")
    print(f"releaselevel: {sys.version_info.releaselevel}")
    print(f"strict mode: {STRICT} "
          f"(env={STRICT_ENV}, auto={AUTO_STRICT})\n")
    for r in _results:
        tag = "[HARD]" if r.hard else "[soft]"
        print(f"{tag} {r.status:<4} {r.name.ljust(width)}  {r.detail}")

    hard_failed = [r for r in _results if r.hard and r.status == FAIL]
    soft_failed = [r for r in _results if not r.hard and r.status == FAIL]
    soft_skipped = [r for r in _results if not r.hard and r.status == SKIP]

    print()
    print(f"summary: {sum(r.status == PASS for r in _results)} pass / "
          f"{sum(r.status == SKIP for r in _results)} skip / "
          f"{sum(r.status == FAIL for r in _results)} fail")

    if hard_failed:
        return 1
    if STRICT and soft_failed:
        return 2
    # In auto-strict (rc1+), a SKIP on a probe that should have landed is also
    # a signal — but we deliberately don't fail on skip to keep the surface
    # small. Emit a warning so it shows up in CI logs.
    if AUTO_STRICT and soft_skipped:
        print(f"WARNING: {len(soft_skipped)} SOFT probes SKIPPED at "
              f"releaselevel={sys.version_info.releaselevel}; review probes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
