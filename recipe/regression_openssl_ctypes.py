#!/usr/bin/env python3
"""Regression checks for openssl 3.5.7 + external libffi feedstock patches.

Patches exercised:
  0028  DER EOF handling in _ssl.c (OpenSSL 3.5.7 returns NOT_ENOUGH_DATA at EOF)
  0015/0029  _ctypes with external libffi on Windows

Demonstrating the SSL failure (vanilla Python 3.10 + openssl >= 3.5.7, without 0028):

  1. Build/install Python with patches 0001-0027 only (omit 0028).
  2. Run:  python regression_openssl_ctypes.py
  3. Expect:  FAIL  ssl_der_eof_single_cert  (SSLError: not enough data)

After applying 0028 and rebuilding, the same command should report all PASS.

The stdlib unittest added by 0028 can also be run directly:

  python -m unittest test.test_ssl.ContextTests.test_load_verify_cadata -v

On Windows, ssl.create_default_context() hits the same DER-EOF path via the
system cert store; test_windows_default_context covers that when win32.
"""

from __future__ import annotations

import os
import re
import sys
import traceback


def _result(name: str, status: str, detail: str = "") -> tuple[str, str, str]:
    return name, status, detail


def _openssl_ge(version: tuple[int, int, int]) -> bool:
    import ssl

    m = re.search(r"OpenSSL (\d+)\.(\d+)\.(\d+)", ssl.OPENSSL_VERSION)
    if not m:
        return False
    return tuple(map(int, m.groups())) >= version


def _load_test_ca_pem() -> str:
    import sysconfig

    stdlib = sysconfig.get_path("stdlib")
    candidates = [
        os.path.join(stdlib, "test", "certdata", "capath", "5ed36f99.0"),
        os.path.join(stdlib, "test", "certdata", "keycert.pem"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            with open(path, encoding="ascii") as f:
                return f.read()
    raise FileNotFoundError(
        "No test CA PEM found under %s; install the python test suite" % stdlib
    )


def test_ssl_der_eof_single_cert() -> tuple[str, str, str]:
    """Single DER cert ending at buffer EOF (core 0028 regression)."""
    name = "ssl_der_eof_single_cert"
    if not _openssl_ge((3, 5, 7)):
        import ssl

        return _result(name, "SKIP", "OpenSSL %s < 3.5.7" % ssl.OPENSSL_VERSION)

    import ssl

    cacert_der = ssl.PEM_cert_to_DER_cert(_load_test_ca_pem())
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    try:
        ctx.load_verify_locations(cadata=cacert_der)
    except ssl.SSLError as exc:
        msg = str(exc)
        if "NOT_ENOUGH_DATA" in msg or "not enough data" in msg.lower():
            return _result(
                name,
                "FAIL",
                "%s (apply patch 0028)" % exc,
            )
        raise
    return _result(name, "PASS", "load_verify_locations accepted DER cadata at EOF")


def test_ssl_der_rejects_trailing_garbage() -> tuple[str, str, str]:
    """DER cert followed by non-EOF byte must raise SSLError (0028 test_ssl addition)."""
    name = "ssl_der_rejects_trailing_garbage"
    if not _openssl_ge((3, 5, 7)):
        import ssl

        return _result(name, "SKIP", "OpenSSL %s < 3.5.7" % ssl.OPENSSL_VERSION)

    import ssl

    cacert_der = ssl.PEM_cert_to_DER_cert(_load_test_ca_pem())
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    try:
        ctx.load_verify_locations(cadata=cacert_der + b"A")
    except ssl.SSLError:
        return _result(name, "PASS", "trailing byte correctly rejected")
    return _result(name, "FAIL", "expected SSLError for DER cert + trailing byte")


def test_windows_default_context() -> tuple[str, str, str]:
    """Windows cert store loads DER via load_verify_locations(cadata=...)."""
    name = "windows_default_context"
    if sys.platform != "win32":
        return _result(name, "SKIP", "Windows only")
    if not _openssl_ge((3, 5, 7)):
        import ssl

        return _result(name, "SKIP", "OpenSSL %s < 3.5.7" % ssl.OPENSSL_VERSION)

    import ssl

    try:
        ssl.create_default_context()
    except ssl.SSLError as exc:
        msg = str(exc)
        if "NOT_ENOUGH_DATA" in msg or "not enough data" in msg.lower():
            return _result(
                name,
                "FAIL",
                "%s (apply patch 0028)" % exc,
            )
        raise
    return _result(name, "PASS", "create_default_context() succeeded")


def test_ctypes_external_libffi_fields() -> tuple[str, str, str]:
    """Exercise ctypes Structure field descriptors (0029 / gh-29791)."""
    name = "ctypes_external_libffi_fields"
    import ctypes

    class Record(ctypes.Structure):
        _fields_ = [
            ("d", ctypes.c_double),
            ("q", ctypes.c_longlong),
            ("p", ctypes.c_void_p),
            ("h", ctypes.c_short),
        ]

    rec = Record()
    rec.d = 2.5
    rec.q = 1 << 40
    rec.h = -3
    if rec.d != 2.5 or rec.q != 1 << 40 or rec.h != -3:
        return _result(name, "FAIL", "field round-trip mismatch")
    return _result(name, "PASS", "Structure fields with external libffi OK")


TESTS = (
    test_ssl_der_eof_single_cert,
    test_ssl_der_rejects_trailing_garbage,
    test_windows_default_context,
    test_ctypes_external_libffi_fields,
)


def main() -> int:
    import ssl

    print("Python:", sys.version.split()[0], "platform:", sys.platform)
    print("OpenSSL:", ssl.OPENSSL_VERSION)
    print()

    failed = 0
    for test in TESTS:
        try:
            name, status, detail = test()
        except Exception:
            failed += 1
            print("FAIL  %s" % test.__name__)
            traceback.print_exc()
            print()
            continue
        line = "%-4s  %s" % (status, name)
        if detail:
            line += "  —  %s" % detail
        print(line)
        if status == "FAIL":
            failed += 1

    print()
    if failed:
        print("%d test(s) failed" % failed)
        return 1
    print("all regression checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
