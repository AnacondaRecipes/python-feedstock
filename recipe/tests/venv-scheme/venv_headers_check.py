"""PKG-19380: a venv created from this Python must expose the base headers/stdlib.

Phase A runs with the base interpreter: it creates a plain venv and re-executes
this script with the venv interpreter. Phase B asserts the paths that setuptools,
Cython, pybind11 and torch.utils.cpp_extension actually read.

Every step prints a marker so a CI log names the failing step directly. No third
party test dependency is required: the C compile check is gated on a compiler
being present and uses the compiler directly.
"""

import os
import shutil
import subprocess
import sys
import sysconfig
import tempfile

PROBE_C = "#include <Python.h>\nint probe(void) { return 0; }\n"


def step(n, text):
    print(f"STEP {n}: {text}", flush=True)


def fail(msg, code=1):
    print(f"FAIL: {msg}", flush=True)
    return code


def phase_base():
    step(0, "base interpreter; creating venv")
    base = tempfile.mkdtemp(prefix="venv-scheme-")
    import venv

    venv.EnvBuilder(with_pip=False, system_site_packages=False).create(base)
    venv_py = os.path.join(base, "Scripts", "python.exe") if os.name == "nt" else os.path.join(base, "bin", "python")
    if not os.path.isfile(venv_py):
        return fail(f"venv interpreter missing at {venv_py}")
    print(f"STEP 0: venv={base}", flush=True)
    return subprocess.call([venv_py, os.path.abspath(__file__), "--in-venv"])


def phase_venv():
    inc = sysconfig.get_path("include")
    platinc = sysconfig.get_path("platinclude")
    std = sysconfig.get_path("stdlib")
    has_h = os.path.isfile(os.path.join(inc, "Python.h"))
    has_os = os.path.isfile(os.path.join(std, "os.py"))

    # The ticket's repro, printed verbatim for the log.
    print(f"DIAG include={inc} Python.h={has_h}", flush=True)
    print(f"DIAG platinclude={platinc}", flush=True)
    print(f"DIAG stdlib={std} os.py={has_os}", flush=True)

    step(1, "running inside a venv")
    if sys.prefix == sys.base_prefix:
        return fail("not running inside a venv")

    step(2, "get_path('include') contains Python.h")
    if not has_h:
        return fail(f"Python.h missing from {inc}")

    step(3, "get_path('stdlib') contains os.py")
    if not has_os:
        return fail(f"os.py missing from {std}")

    step(4, "config vars used by setuptools/Cython/pybind11/torch")
    # sysconfig computes these at import time from the default scheme, which is
    # the venv scheme here -- exactly what a compiler front end consumes.
    # LIBDEST only exists on Windows; on POSIX the value is absent, not wrong.
    for var in ("INCLUDEPY", "LIBDEST"):
        value = sysconfig.get_config_var(var)
        print(f"DIAG {var}={value}", flush=True)
        if value is None:
            continue
        if not os.path.isdir(value):
            return fail(f"{var} does not resolve to a directory: {value!r}")
        if not os.listdir(value):
            return fail(f"{var} points at an empty directory: {value!r}")
    incpy = sysconfig.get_config_var("INCLUDEPY")
    if not incpy or not os.path.isfile(os.path.join(incpy, "Python.h")):
        return fail(f"INCLUDEPY does not contain Python.h: {incpy!r}")

    step(5, "compile a C file against the venv header paths")
    cc = os.environ.get("CC") or shutil.which("cl") or shutil.which("gcc") or shutil.which("cc")
    if not cc:
        print("SKIP: no compiler on PATH (CC unset); header paths verified above", flush=True)
        return 0
    work = tempfile.mkdtemp(prefix="venv-scheme-cc-")
    src = os.path.join(work, "probe.c")
    with open(src, "w") as f:
        f.write(PROBE_C)
    if os.path.basename(cc).lower().startswith("cl"):
        cmd = [cc, "/nologo", "/c", f"/I{inc}", f"/I{platinc}", src, f"/Fo{os.path.join(work, 'probe.obj')}"]
    else:
        cmd = [cc, "-c", f"-I{inc}", f"-I{platinc}", src, "-o", os.path.join(work, "probe.o")]
    print(f"DIAG compile={' '.join(cmd)}", flush=True)
    proc = subprocess.run(cmd, cwd=work, capture_output=True, text=True, errors="replace")
    if proc.returncode != 0:
        print(proc.stdout[-2000:], flush=True)
        print(proc.stderr[-2000:], flush=True)
        return fail(f"compile against {inc} failed")
    print("PASS: venv exposes headers, stdlib and config vars; compile ok", flush=True)
    return 0


def main():
    if "--in-venv" in sys.argv:
        return phase_venv()
    return phase_base()


if __name__ == "__main__":
    sys.exit(main())
