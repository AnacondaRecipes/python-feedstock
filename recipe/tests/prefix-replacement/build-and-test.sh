#!/usr/bin/env bash

set -ex

# After C17, python3-config --embed prefers the shared lib (sysconfig from the
# shared build). libpython-static tests must link libpython*.a explicitly.

if [[ "$PKG_NAME" == "libpython-static" ]]; then
  STATIC_LIB=$(ls ${CONDA_PREFIX}/lib/libpython*.a | grep -v nolto | head -1)
  EMBED_LDFLAGS=$(python3-config --embed --ldflags | sed -E 's/-lpython[^ ]*//g')
  # see bpo44182 for why -L${CONDA_PREFIX}/lib is added
  ${CC} a.c $(python3-config --cflags) "${STATIC_LIB}" ${EMBED_LDFLAGS} -L${CONDA_PREFIX}/lib -o ${CONDA_PREFIX}/bin/embedded-python-static
  if [[ "$target_platform" == linux-* ]]; then
    if ${READELF} -d ${CONDA_PREFIX}/bin/embedded-python-static | rg 'NEEDED.*libpython'; then
      echo "ERROR :: Embedded python linked to shared python library. It is expected to link to the static library."
      exit 1
    fi
  elif [[ "$target_platform" == osx-* ]]; then
    if ${OTOOL} -L ${CONDA_PREFIX}/bin/embedded-python-static | rg 'libpython.*\.(so|dylib)'; then
      echo "ERROR :: Embedded python linked to shared python library. It is expected to link to the static library."
      exit 1
    fi
  fi
  ${CONDA_PREFIX}/bin/embedded-python-static

  # Shared embed needs libpython*.so/.dylib (separate output). Skip if absent.
  shopt -s nullglob
  _shared=( ${CONDA_PREFIX}/lib/libpython*.so ${CONDA_PREFIX}/lib/libpython*.dylib )
  shopt -u nullglob
  if [[ ${#_shared[@]} -eq 0 ]]; then
    echo "Skipping shared-embed check: no libpython shared lib in prefix."
    set +x
    exit 0
  fi
  rm -rf ${CONDA_PREFIX}/lib/libpython*.a
fi

${CC} a.c $(python3-config --cflags) \
    $(python3-config --embed --ldflags) \
    -L${CONDA_PREFIX}/lib -Wl,-rpath,${CONDA_PREFIX}/lib \
    -o ${CONDA_PREFIX}/bin/embedded-python-shared

if [[ "$target_platform" == linux-* ]]; then
  if ! ${READELF} -d ${CONDA_PREFIX}/bin/embedded-python-shared | rg 'NEEDED.*libpython'; then
    echo "ERROR :: Embedded python linked to static python library. We tried to force it to use the shared library."
    exit 1
  fi
elif [[ "$target_platform" == osx-* ]]; then
  if ! ${OTOOL} -L ${CONDA_PREFIX}/bin/embedded-python-shared | rg 'libpython.*\.(so|dylib)'; then
    echo "ERROR :: Embedded python linked to static python library. We tried to force it to use the shared library."
    exit 1
  fi
fi
${CONDA_PREFIX}/bin/embedded-python-shared

set +x
