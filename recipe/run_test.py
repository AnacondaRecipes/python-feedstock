import os
import platform
import sys
import subprocess

armv6l = bool(platform.machine() == 'armv6l')
armv7l = bool(platform.machine() == 'armv7l')
ppc64le = bool(platform.machine() == 'ppc64le')
if sys.platform == 'darwin':
    osx105 = b'10.5.' in subprocess.check_output('sw_vers')
else:
    osx105 = False

print('sys.version:', sys.version)
print('sys.platform:', sys.platform)
print('tuple.__itemsize__:', tuple.__itemsize__)
if sys.platform == 'win32':
    assert 'MSC v.19' in sys.version
print('sys.maxunicode:', sys.maxunicode)
print('platform.architecture:', platform.architecture())
print('platform.python_version:', platform.python_version())

import _bisect
import _codecs_cn
import _codecs_hk
import _codecs_iso2022
import _codecs_jp
import _codecs_kr
import _codecs_tw
import _collections
import _csv
import _ctypes
import _ctypes_test
import _decimal
import _elementtree
import _functools
import _hashlib
import _heapq
import _io
import _json
import _locale
import _lsprof
import _lzma
import _multibytecodec
import _multiprocessing
import _random
import _socket
import _sqlite3
import _ssl
import _struct
import _testcapi
import array
import audioop
import binascii
import bz2
import cmath
import datetime
import itertools
import lzma
import math
import mmap
import operator
import pyexpat
import select
import time
import test
import test.support
import unicodedata
import zlib
from os import urandom
import os

t = 100 * b'Foo '
assert lzma.decompress(lzma.compress(t)) == t

if sys.platform != 'win32':
    if not (ppc64le or armv7l):
        import _curses
        import _curses_panel
    import fcntl
    import grp
    import readline
    import resource
    import syslog
    import termios


if not (armv6l or armv7l or ppc64le or osx105):
    import tkinter
    import turtle
    import _tkinter
    print('TK_VERSION: %s' % _tkinter.TK_VERSION)
    print('TCL_VERSION: %s' % _tkinter.TCL_VERSION)
    TCLTK_VER = os.getenv("tk")
    assert _tkinter.TK_VERSION == _tkinter.TCL_VERSION == TCLTK_VER

import ssl
print('OPENSSL_VERSION:', ssl.OPENSSL_VERSION)
CONDA_OPENSSL_VERSION = os.getenv("openssl")
assert CONDA_OPENSSL_VERSION in ssl.OPENSSL_VERSION
# xref https://github.com/conda-forge/openssl-feedstock/issues/237
from pathlib import Path
pem = Path(__file__).with_name("test-cert.pem").read_text()
der = ssl.PEM_cert_to_DER_cert(pem)
ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
ctx.load_verify_locations(cadata=der)

# CVE-2026-115557 (gh-160040): a peer chain signed by a compromised eMudhra
# intermediate must be rejected even though the chain itself is valid.
import tempfile
import zipfile

fixtures = Path(__file__).with_name("tests") / "ssl"
with tempfile.TemporaryDirectory() as tmpdir:
    # The archive is encrypted only so the test certs are not stored in the
    # clear; the password is fixed and public.
    with zipfile.ZipFile(fixtures / "distrusted.zip") as zf:
        zf.extractall(tmpdir, pwd=b"Brave Sir Robin")
    distrusted = Path(tmpdir) / "distrusted"
    client_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    server_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    client_ctx.load_verify_locations(str(distrusted / "distrusted_root.pem"))
    server_ctx.load_cert_chain(str(distrusted / "distrusted_keycert.pem"))

    c_in, c_out = ssl.MemoryBIO(), ssl.MemoryBIO()
    s_in, s_out = ssl.MemoryBIO(), ssl.MemoryBIO()
    client = client_ctx.wrap_bio(c_in, c_out, server_hostname="localhost")
    server = server_ctx.wrap_bio(s_in, s_out, server_side=True)
    try:
        for _ in range(5):
            try:
                client.do_handshake()
            except ssl.SSLWantReadError:
                pass
            if c_out.pending:
                s_in.write(c_out.read())
            try:
                server.do_handshake()
            except ssl.SSLWantReadError:
                pass
            if s_out.pending:
                c_in.write(s_out.read())
        client.do_handshake()
    except ssl.SSLCertVerificationError as exc:
        assert exc.verify_code == 28, exc  # X509_V_ERR_CERT_REJECTED
    else:
        raise AssertionError("distrusted eMudhra chain was accepted")
print("distrusted SPKI check: OK")
