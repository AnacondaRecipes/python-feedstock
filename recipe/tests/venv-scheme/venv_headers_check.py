"""PKG-19380 T2/T5: run with the interpreter of a venv created from this Python.

Prints the ticket's repro values (T5, diagnostic), then asserts that the venv
exposes Python.h and the stdlib, and that a C extension builds against them.
"""

import os
import subprocess
import sys
import sysconfig
import tempfile

PROBE_C = r"""
#include <Python.h>
static struct PyModuleDef moduledef = {PyModuleDef_HEAD_INIT, "probe", NULL, -1, NULL};
PyMODINIT_FUNC PyInit_probe(void) { return PyModule_Create(&moduledef); }
"""

SETUP_PY = """
from setuptools import setup, Extension
setup(name="probe", ext_modules=[Extension("probe", ["probe.c"])])
"""


def main():
    inc = sysconfig.get_path("include")
    std = sysconfig.get_path("stdlib")
    has_h = os.path.isfile(os.path.join(inc, "Python.h"))
    has_os = os.path.isfile(os.path.join(std, "os.py"))

    # T5 diagnostic: the ticket repro, printed for the CI log.
    print(f"DIAG include={inc} Python.h={has_h}")
    print(f"DIAG stdlib={std} os.py={has_os}")

    if sys.prefix == sys.base_prefix:
        print("ERROR: must run inside a venv")
        return 2
    if not has_h:
        print(f"FAIL: Python.h missing from {inc}")
        return 1
    if not has_os:
        print(f"FAIL: os.py missing from {std}")
        return 1

    with tempfile.TemporaryDirectory() as work:
        with open(os.path.join(work, "probe.c"), "w") as f:
            f.write(PROBE_C)
        with open(os.path.join(work, "setup.py"), "w") as f:
            f.write(SETUP_PY)
        proc = subprocess.run(
            [sys.executable, "setup.py", "build_ext", "--inplace"],
            cwd=work, capture_output=True, text=True,
        )
        if proc.returncode != 0:
            print("FAIL: C extension build inside venv failed")
            print(proc.stdout[-4000:])
            print(proc.stderr[-4000:])
            return 1
    print("PASS: venv headers, stdlib and C extension build")
    return 0


if __name__ == "__main__":
    sys.exit(main())
