"""PKG-19380: the nt_venv install scheme must describe the base install.

Run twice on Windows: with the base interpreter (scheme contract) and with a
plain venv created from it (what setuptools, Cython, pybind11 and torch see).
Stdlib only, so it runs in any test env, including free-threaded builds.
"""

import os
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import unittest

IN_VENV = sys.prefix != sys.base_prefix
PROBE_C = "#include <Python.h>\nint probe(void) { return 0; }\n"

# Expected nt_conda block (CFEP-65). nt_venv must mirror its base-install keys.
NT_CONDA = {
    "stdlib": "{installed_base}/{platlibdir}/{implementation_lower}",
    "platstdlib": "{base}/{platlibdir}/{implementation_lower}",
    "purelib": "{base}/lib/{implementation_lower}/site-packages",
    "platlib": "{base}/{platlibdir}/{implementation_lower}/site-packages",
    "include": "{installed_base}/include/{implementation_lower}",
    "platinclude": "{installed_platbase}/include/{implementation_lower}",
    "scripts": "{base}/Scripts",
    "data": "{base}",
}


class SchemeContract(unittest.TestCase):
    """nt_venv is the venv scheme. Base-install keys must match nt_conda."""

    def setUp(self):
        self.venv = sysconfig.get_paths("nt_venv")
        self.conda = sysconfig.get_paths("nt_conda")

    def test_stdlib_matches_base_layout(self):
        self.assertEqual(self.venv["stdlib"], self.conda["stdlib"])

    def test_include_and_platinclude_match_base_layout(self):
        self.assertEqual(self.venv["include"], self.conda["include"])
        self.assertEqual(self.venv["platinclude"], self.conda["platinclude"])

    def test_venv_local_paths_unchanged(self):
        local = lambda *p: os.path.normpath(os.path.join(sys.prefix, *p))
        self.assertEqual(self.venv["purelib"], local("Lib", "site-packages"))
        self.assertEqual(self.venv["platlib"], local("Lib", "site-packages"))
        self.assertEqual(self.venv["scripts"], local("Scripts"))
        self.assertEqual(self.venv["data"], local())

    def test_nt_conda_block_unchanged(self):
        self.assertEqual(sysconfig.get_paths("nt_conda", expand=False), NT_CONDA)

    def test_venv_alias_is_nt_venv(self):
        self.assertEqual(sysconfig.get_paths("venv"), self.venv)

    def test_prefix_scheme_selection(self):
        expected = "venv" if IN_VENV else "nt_conda"
        self.assertEqual(sysconfig.get_preferred_scheme("prefix"), expected)


class HeadersInstalled(unittest.TestCase):
    """What a compiler and build backend actually consume, in base and venv."""

    def test_include_has_python_h(self):
        self.assertTrue(os.path.isfile(os.path.join(sysconfig.get_path("include"), "Python.h")),
                        sysconfig.get_path("include"))

    def test_stdlib_has_os_py(self):
        self.assertTrue(os.path.isfile(os.path.join(sysconfig.get_path("stdlib"), "os.py")),
                        sysconfig.get_path("stdlib"))

    def test_config_vars_point_at_headers(self):
        # setuptools and distutils read INCLUDEPY, which is computed from the active scheme.
        incpy = sysconfig.get_config_var("INCLUDEPY")
        self.assertTrue(os.path.isfile(os.path.join(incpy, "Python.h")), incpy)

    def test_c_extension_compiles(self):
        cc = os.environ.get("CC") or shutil.which("cl") or shutil.which("gcc")
        if not cc:
            self.skipTest("no C compiler on PATH")
        inc = sysconfig.get_path("include")
        is_msvc = os.path.splitext(os.path.basename(cc))[0].lower() == "cl"
        with tempfile.TemporaryDirectory() as work:
            src = os.path.join(work, "probe.c")
            with open(src, "w") as f:
                f.write(PROBE_C)
            if is_msvc:
                cmd = [cc, "/nologo", "/c", f"/I{inc}", src, f"/Fo{os.path.join(work, 'probe.obj')}"]
            else:
                cmd = [cc, "-c", f"-I{inc}", src, "-o", os.path.join(work, "probe.o")]
            proc = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
