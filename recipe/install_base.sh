#!/bin/bash
set -ex

cd ${SRC_DIR}
export PATH=${SRC_DIR}/python-bin/bin:${PATH}
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
_buildd_static=build-static
_buildd_shared=build-shared

make -C ${_buildd_static} install

declare -a _FLAGS_REPLACE=()
if [[ ${DEBUG_C} != yes ]]; then
  _FLAGS_REPLACE+=(-O3)
  _FLAGS_REPLACE+=(-O2)
  _FLAGS_REPLACE+=("-fprofile-use")
  _FLAGS_REPLACE+=("")
  _FLAGS_REPLACE+=("-fprofile-correction")
  _FLAGS_REPLACE+=("")
  _FLAGS_REPLACE+=("-L.")
  _FLAGS_REPLACE+=("")
  if [[ ${CC} =~ .*gcc.* ]]; then
    for flag in -fuse-linker-plugin -ffat-lto-objects -flto-partition=none -flto; do
      _FLAGS_REPLACE+=("${flag}" "")
    done
  else
    _FLAGS_REPLACE+=(-flto "")
  fi
fi

SYSCONFIG=$(find ${_buildd_static}/$(cat ${_buildd_static}/pybuilddir.txt) -name "_sysconfigdata*.py" -print0)
cat ${SYSCONFIG} | ${SYS_PYTHON} "${RECIPE_DIR}"/replace-word-pairs.py \
  "${_FLAGS_REPLACE[@]}"  \
    > ${PREFIX}/lib/python${VERABI}/$(basename ${SYSCONFIG})
MAKEFILE=$(find ${PREFIX}/lib/python${VERABI}/ -path "*config-*/Makefile" -print0)
cp ${MAKEFILE} /tmp/Makefile-$$
cat /tmp/Makefile-$$ | ${SYS_PYTHON} "${RECIPE_DIR}"/replace-word-pairs.py \
  "${_FLAGS_REPLACE[@]}"  \
    > ${MAKEFILE}

if [[ -f ${PREFIX}/bin/python${VER}m ]]; then
  rm -f ${PREFIX}/bin/python${VER}m
  ln -s ${PREFIX}/bin/python${VER} ${PREFIX}/bin/python${VER}m
fi
ln -s ${PREFIX}/bin/python${VER} ${PREFIX}/bin/python
ln -s ${PREFIX}/bin/pydoc${VER} ${PREFIX}/bin/pydoc
ln -s ${PREFIX}/bin/python3.14 ${PREFIX}/bin/python3.1

pushd ${PREFIX}/lib/python${VERABI}
  mkdir test_keep
  mv test/__init__.py test/support test/test_support* test/test_script_helper* test_keep/
  rm -rf test */test
  mv test_keep test
popd

pushd ${PREFIX}
  if [[ -f lib/libpython${VERABI}.a ]]; then
    chmod +w lib/libpython${VERABI}.a
    ${STRIP} -S lib/libpython${VERABI}.a
  fi
  CONFIG_LIBPYTHON=$(find lib/python${VERABI}/config-${VERABI}* -name "libpython${VERABI}.a")
  if [[ -f lib/libpython${VERABI}.a ]] && [[ -f ${CONFIG_LIBPYTHON} ]]; then
    chmod +w ${CONFIG_LIBPYTHON}
    rm ${CONFIG_LIBPYTHON}
  fi
popd

case "$target_platform" in
  linux-64)
    OLD_HOST=$(echo ${HOST} | sed -e 's/-conda-/-conda_cos6-/g')
    ;;
  linux-*)
    OLD_HOST=$(echo ${HOST} | sed -e 's/-conda-/-conda_cos7-/g')
    ;;
  *)
    OLD_HOST=$HOST
    ;;
esac

pushd "${PREFIX}"/lib/python${VERABI}
  find lib-dynload -name "_sysconfigdata*.py*" -exec rm {} \;
  recorded_name=$(find . -name "_sysconfigdata*.py")
  our_compilers_name=_sysconfigdata_$(echo ${HOST} | sed -e 's/[.-]/_/g').py
  cp ${recorded_name} ${recorded_name}.orig
  cp ${recorded_name} sysconfigfile
  sed -i.bak "s@-fdebug-prefix-map=$SRC_DIR=/usr/local/src/conda/python-$PKG_VERSION@@g" sysconfigfile
  sed -i.bak "s@-fdebug-prefix-map=$PREFIX=/usr/local/src/conda-prefix@@g" sysconfigfile
  sed -i.bak "s@zoneinfo'@zoneinfo:$PREFIX/share/tzinfo'@g" sysconfigfile
  sed -i.bak "s@-isysroot @@g" sysconfigfile
  if [[ ${HOST} =~ .*darwin.* ]] && [[ -n ${CONDA_BUILD_SYSROOT} ]]; then
    sed -i.bak "s@$CONDA_BUILD_SYSROOT @@g" sysconfigfile
  fi
  sed -i.bak "s/@SGI_ABI@//g" sysconfigfile
  sed -i.bak "s@$BUILD_PREFIX/bin/${HOST}-llvm-ar@${HOST}-ar@g" sysconfigfile
  sed -i.bak "s/'GNULD': 'yes'/'GNULD': 'no'/g" sysconfigfile
  cp sysconfigfile ${our_compilers_name}
  sed -i.bak "s@${HOST}@${OLD_HOST}@g" sysconfigfile
  old_compiler_name=_sysconfigdata_$(echo ${OLD_HOST} | sed -e 's/[.-]/_/g').py
  cp sysconfigfile ${old_compiler_name}
  sed -i.bak "s@$OLD_HOST-c++@g++@g" sysconfigfile
  sed -i.bak "s@$OLD_HOST-@@g" sysconfigfile
  if [[ "$target_platform" == linux* ]]; then
    sed -i.bak "s@-pthread@-pthread -B $PREFIX/compiler_compat@g" sysconfigfile
  fi
  sed -i.bak "s@-march=[^( |\\\"|\\\')]*@@g" sysconfigfile
  sed -i.bak "s@-mtune=[^( |\\\"|\\\')]*@@g" sysconfigfile
  for flag in "-fstack-protector-strong" "-ffunction-sections" "-pipe" "-fno-plt" \
             "-ftree-vectorize" "-Wl,--sort-common" "-Wl,--as-needed" "-Wl,-z,relro" \
             "-Wl,-z,now" "-Wl,--disable-new-dtags" "-Wl,--gc-sections" "-Wl,-O2" \
             "-fPIE" "-ftree-vectorize" "-mssse3" "-Wl,-pie" "-Wl,-dead_strip_dylibs" \
             "-Wl,-headerpad_max_install_names"; do
    sed -i.bak "s@$flag@@g" sysconfigfile
  done
  sed -i.bak "s@' [ ]*@'@g" sysconfigfile
  cp sysconfigfile $recorded_name
  echo "========================sysconfig==========================="
  cat $recorded_name
  echo "============================================================"
  rm sysconfigfile
  rm sysconfigfile.bak
popd

if [[ ${HOST} =~ .*linux.* ]]; then
  mkdir -p ${PREFIX}/compiler_compat
  ln -s ${PREFIX}/bin/${HOST}-ld ${PREFIX}/compiler_compat/ld
  echo "Files in this folder are to enhance backwards compatibility of anaconda software with older compilers."   > ${PREFIX}/compiler_compat/README
  echo "See: https://github.com/conda/conda/issues/6030 for more information."                                   >> ${PREFIX}/compiler_compat/README
fi

python -c "import compileall,os;compileall.compile_dir(os.environ['PREFIX'])"
rm ${PREFIX}/lib/libpython${VERABI}.a
if [[ "$target_platform" == linux-* ]]; then
  rm ${PREFIX}/include/uuid.h
fi

SP_DIR="${PREFIX}/lib/python${PY_VER}${THREAD}/site-packages"
if [[ ${PY_GIL_DISABLED} == yes ]]; then
    echo "${PREFIX}/lib/python${PY_VER}/site-packages" >> $SP_DIR/conda-site.pth
fi
echo "${PREFIX}/lib/python3.1/site-packages" >> $SP_DIR/conda-site.pth
echo "${PREFIX}/lib/python/site-packages" >> $SP_DIR/conda-site.pth
