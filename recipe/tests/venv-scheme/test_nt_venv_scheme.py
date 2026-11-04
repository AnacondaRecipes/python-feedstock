"""PKG-19380: the nt_venv install scheme must describe the base install.

Run with the base (non-venv) interpreter on Windows. The nt_venv scheme is what
sysconfig uses inside any venv created from this Python, so its stdlib and
include paths must match the nt_conda layout that the base install ships.
"""

import os
import sys
import sysconfig
import unittest


def _venv_local(*parts):
    return os.path.normpath(os.path.join(sys.prefix, *parts))


class NtVenvSchemeTests(unittest.TestCase):
    def setUp(self):
        self.venv = sysconfig.get_paths("nt_venv")
        self.conda = sysconfig.get_paths("nt_conda")

    def test_stdlib_matches_base_layout(self):
        self.assertEqual(self.venv["stdlib"], self.conda["stdlib"])

    def test_stdlib_contains_os_py(self):
        self.assertTrue(os.path.isfile(os.path.join(self.venv["stdlib"], "os.py")),
                        self.venv["stdlib"])

    def test_include_matches_base_layout(self):
        self.assertEqual(self.venv["include"], self.conda["include"])

    def test_platinclude_matches_base_layout(self):
        self.assertEqual(self.venv["platinclude"], self.conda["platinclude"])

    def test_include_contains_python_h(self):
        self.assertTrue(os.path.isfile(os.path.join(self.venv["include"], "Python.h")),
                        self.venv["include"])

    def test_venv_local_site_packages_and_scripts_unchanged(self):
        self.assertEqual(self.venv["purelib"], _venv_local("Lib", "site-packages"))
        self.assertEqual(self.venv["platlib"], _venv_local("Lib", "site-packages"))
        self.assertEqual(self.venv["scripts"], _venv_local("Scripts"))
        self.assertEqual(self.venv["data"], _venv_local())

    def test_venv_alias_points_at_nt_venv(self):
        self.assertEqual(sysconfig.get_paths("venv"), self.venv)

    def test_nt_conda_block_is_unchanged(self):
        expected = {
            "stdlib": "{installed_base}/{platlibdir}/{implementation_lower}",
            "platstdlib": "{base}/{platlibdir}/{implementation_lower}",
            "purelib": "{base}/lib/{implementation_lower}/site-packages",
            "platlib": "{base}/{platlibdir}/{implementation_lower}/site-packages",
            "include": "{installed_base}/include/{implementation_lower}",
            "platinclude": "{installed_platbase}/include/{implementation_lower}",
            "scripts": "{base}/Scripts",
            "data": "{base}",
        }
        self.assertEqual(sysconfig.get_paths("nt_conda", expand=False), expected)

    def test_default_scheme_include_contains_python_h(self):
        # Outside a venv the default (nt_conda) scheme must already work (CFEP-65).
        if sys.prefix != sys.base_prefix:
            self.skipTest("run with the base interpreter")
        self.assertTrue(os.path.isfile(os.path.join(sysconfig.get_path("include"), "Python.h")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
