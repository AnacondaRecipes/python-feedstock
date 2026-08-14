# https://scikit-build-core.readthedocs.io/en/latest/guide/cmakelists.html#finding-python

cmake_minimum_required(VERSION 3.10)
enable_language(C)
project(mymath)

# Must be STRING cache vars — option() is boolean and expands to OFF as a
# bogus find_package component ("Could NOT find Python (missing: OFF)").
set(PY_VER "" CACHE STRING "Python version to use")
set(EXTRA_COMPONENTS "" CACHE STRING "Additional Python components to check for")

# Since 3.16, CMake does not accept freethreaded interpreter by default
# anymore. Allow it explicitly.
# https://cmake.org/cmake/help/latest/module/FindPython.html#hints
set(Python_FIND_ABI "ANY" "ANY" "ANY" "ANY")
find_package(Python ${PY_VER} COMPONENTS Interpreter ${EXTRA_COMPONENTS} REQUIRED)
