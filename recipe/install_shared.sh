#!/bin/bash
set -ex

cd ${SRC_DIR}
VER=${PKG_VERSION%.*}
if [[ ${PY_GIL_DISABLED} == yes ]]; then
  THREAD=t
else
  THREAD=
fi
if [[ ${DEBUG_PY} == yes ]]; then
  DBG=d
else
  DBG=
fi
VERABI=${VER}${THREAD}${DBG}

shopt -s extglob
cp -pf build-shared/libpython*${SHLIB_EXT}!(.lto) ${PREFIX}/lib/
shopt -u extglob
if [[ ${target_platform} == linux-* ]]; then
  ln -sf ${PREFIX}/lib/libpython${VERABI}${SHLIB_EXT}.1.0 ${PREFIX}/lib/libpython${VERABI}${SHLIB_EXT}
fi
