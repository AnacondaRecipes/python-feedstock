#!/usr/bin/env bash

set -ex

case ${PKG_NAME} in
  libpython)
    # see bpo44182 for why -L${CONDA_PREFIX}/lib is added
    ${CC} a.c $(python3-config --cflags) \
        $(python3-config --embed --ldflags) \
        -L${CONDA_PREFIX}/lib -Wl,-rpath,${CONDA_PREFIX}/lib \
        -o ${CONDA_PREFIX}/bin/embedded-python-shared

    if [[ "$target_platform" == linux-* ]]; then
      if ! ${READELF} -d ${CONDA_PREFIX}/bin/embedded-python-shared | rg '\(NEEDED\).*\[libpython[^]]*\]'; then
        echo "ERROR :: Embedded python linked to static python library. We tried to force it to use the shared library."
        exit 1
      fi
    elif [[ "$target_platform" == osx-* ]]; then
      if ! ${OTOOL} -L ${CONDA_PREFIX}/bin/embedded-python-shared | rg '^[[:space:]]+[^[:space:]]*/libpython[^[:space:]]*\.dylib[[:space:]]'; then
        echo "ERROR :: Embedded python linked to static python library. We tried to force it to use the shared library."
        exit 1
      fi
    fi
    ${CONDA_PREFIX}/bin/embedded-python-shared
    ;;

  libpython-static)
    ${CC} a.c $(python3-config --cflags) \
      $(python3-config --embed --ldflags) \
      -L${CONDA_PREFIX}/lib -Wl,-rpath,${CONDA_PREFIX}/lib \
      -o ${CONDA_PREFIX}/bin/embedded-python-static
    if [[ "$target_platform" == linux-* ]]; then
      if ${READELF} -d ${CONDA_PREFIX}/bin/embedded-python-static | rg '\(NEEDED\).*\[libpython[^]]*\]'; then
        echo "ERROR :: Embedded python linked to shared python library. It is expected to link to the static library."
        exit 1
      fi
    elif [[ "$target_platform" == osx-* ]]; then
      if ${OTOOL} -L ${CONDA_PREFIX}/bin/embedded-python-static | rg '^[[:space:]]+[^[:space:]]*/libpython[^[:space:]]*\.dylib[[:space:]]'; then
        echo "ERROR :: Embedded python linked to shared python library. It is expected to link to the static library."
        exit 1
      fi
    fi
    ${CONDA_PREFIX}/bin/embedded-python-static
    ;;

  *)
    # invalid package
    exit 1
    ;;
esac

set +x
