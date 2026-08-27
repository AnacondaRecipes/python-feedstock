setlocal EnableDelayedExpansion
echo on

:: Avoids fetching nuget.exe from the internet.
set PYTHON=%CONDA_PYTHON_EXE%

:: Compile python, extensions and external libraries
:: win-arm64: ARCH=arm64 from conda-build (see PR #240 / main-3.14).
if "%ARCH%"=="arm64" (
   set PLATFORM=ARM64
   set VC_PATH=arm64
   set BUILD_PATH=arm64
) else if "%ARCH%"=="64" (
   set PLATFORM=x64
   set VC_PATH=x64
   set BUILD_PATH=amd64
) else (
   set PLATFORM=Win32
   set VC_PATH=x86
   set BUILD_PATH=win32
)

for /F "tokens=1,2 delims=." %%i in ("%PKG_VERSION%") do (
  set "VERNODOTS=%%i%%j"
)

for /F "tokens=1,2 delims=." %%i in ("%PKG_VERSION%") do (
  set "VER=%%i.%%j"
)

::  Make sure the "python" value in conda_build_config.yaml is up to date.
for /F "tokens=1,2 delims=." %%i in ("%PKG_VERSION%") do (
  if NOT "%PY_VER%"=="%%i.%%j" exit 1
)

for /f "usebackq delims=" %%i in (`conda list -p %PREFIX% sqlite --no-show-channel-urls --json ^| findstr "version"`) do set SQLITE3_VERSION_LINE=%%i
for /f "tokens=2 delims==/ " %%i IN ('echo %SQLITE3_VERSION_LINE%') do (set SQLITE3_VERSION=%%~i)
echo SQLITE3_VERSION detected as %SQLITE3_VERSION%

if "%PY_INTERP_DEBUG%"=="yes" (
  set CONFIG=-d
  set _D=_d
) else (
  set CONFIG=
  set _D=
)


if "%DEBUG_C%"=="yes" (
  set PGO=
) else (
  set PGO=--pgo
)

:: AP doesn't support PGO atm?
set PGO=

if "%PY_FREETHREADING%" == "yes" (
  set "FREETHREADING=--disable-gil"
  set "THREAD=t"
  set "EXE_T=%VER%t"
  :: Free-threaded MSBuild output goes to PCbuild\amd64t\ / arm64t\ / win32t\,
  :: not the non-t dirs. Upstream python.props sets BuildPath*t when DisableGil=true;
  :: BUILD_PATH below stages those files into %PREFIX% — wrong path → xcopy miss.
  set BUILD_PATH=%BUILD_PATH%t
) else (
  set "FREETHREADING=--experimental-jit-off"
  set "THREAD="
  set "EXE_T="
)

:: Pin Tcl/Tk from the `tk` CBC variant (feedstock overrides aggregate 8.6 → 9.0;
:: host tk 9.0.4 from pkgs/main). Upstream tcltk.props
:: with TclMajorVersion=9 sets tkPrefix=tcl9 → tcl90.lib / tcl9tk90.lib (no threaded t).
set TCLTK_MSBUILD_PROPS="/p:TclVersion=%tk%" "/p:TkVersion=%tk%"

cd PCbuild

:: Twice because:
:: error : importlib_zipimport.h updated. You will need to rebuild pythoncore to see the changes.
call build.bat %PGO% %CONFIG% %FREETHREADING% -m -e -v -p %PLATFORM% %TCLTK_MSBUILD_PROPS%
if errorlevel 1 exit 1
call build.bat %PGO% %CONFIG% %FREETHREADING% -m -e -v -p %PLATFORM% %TCLTK_MSBUILD_PROPS%
if errorlevel 1 exit 1
cd ..

:: Populate the root package directory
for %%x in (python%VERNODOTS%%THREAD%%_D%.dll python3%THREAD%%_D%.dll python%EXE_T%%_D%.exe pythonw%EXE_T%%_D%.exe) do (
  if exist %SRC_DIR%\PCbuild\%BUILD_PATH%\%%x (
    copy /Y %SRC_DIR%\PCbuild\%BUILD_PATH%\%%x %PREFIX%
  ) else (
    echo "WARNING :: %SRC_DIR%\PCbuild\%BUILD_PATH%\%%x does not exist"
  )
)

for %%x in (python%THREAD%%_D%.pdb python%VERNODOTS%%THREAD%%_D%.pdb pythonw%THREAD%%_D%.pdb) do (
  if exist %SRC_DIR%\PCbuild\%BUILD_PATH%\%%x (
    copy /Y %SRC_DIR%\PCbuild\%BUILD_PATH%\%%x %PREFIX%
  ) else (
    echo "WARNING :: %SRC_DIR%\PCbuild\%BUILD_PATH%\%%x does not exist"
  )
)

@echo on

mkdir %PREFIX%\lib\python
copy %SRC_DIR%\LICENSE %PREFIX%\lib\python\LICENSE_PYTHON.txt
if errorlevel 1 exit 1

:: Populate the DLLs directory
mkdir %PREFIX%\lib\python\lib-dynload
xcopy /s /y %SRC_DIR%\PCBuild\%BUILD_PATH%\*.pyd %PREFIX%\lib\python\lib-dynload
if errorlevel 1 exit 1

copy /Y %SRC_DIR%\PC\icons\py.ico %PREFIX%\lib\python\lib-dynload
if errorlevel 1 exit 1
copy /Y %SRC_DIR%\PC\icons\pyc.ico %PREFIX%\lib\python\lib-dynload
if errorlevel 1 exit 1

mkdir %PREFIX%\lib\python\Tools
xcopy /s /y /i %SRC_DIR%\Tools\scripts %PREFIX%\lib\python\Tools\scripts
if errorlevel 1 exit 1

del %PREFIX%\lib\python\Tools\scripts\README
if errorlevel 1 exit 1
del %PREFIX%\lib\python\Tools\scripts\idle3
if errorlevel 1 exit 1

move /y %PREFIX%\lib\python\Tools\scripts\pydoc3 %PREFIX%\lib\python\Tools\scripts\pydoc3.py
if errorlevel 1 exit 1

:: Populate the include directory
mkdir %PREFIX%\include\python
xcopy /s /y %SRC_DIR%\Include %PREFIX%\include\python\
if errorlevel 1 exit 1

:: Copy generated pyconfig.h
copy /Y %SRC_DIR%\PC\pyconfig.h %PREFIX%\include\python\
if errorlevel 1 exit 1

:: Populate the Scripts directory
if not exist %SCRIPTS% (mkdir %SCRIPTS%)
if errorlevel 1 exit 1

for %%x in (idle pydoc) do (
    copy /Y %SRC_DIR%\Tools\scripts\%%x3 %SCRIPTS%\%%x
    if errorlevel 1 exit 1
)

:: Populate the libs directory
if exist %SRC_DIR%\PCbuild\%BUILD_PATH%\python%VERNODOTS%%THREAD%%_D%.lib copy /Y %SRC_DIR%\PCbuild\%BUILD_PATH%\python%VERNODOTS%%THREAD%%_D%.lib %PREFIX%\lib\
if errorlevel 1 exit 1
if exist %SRC_DIR%\PCbuild\%BUILD_PATH%\python3%THREAD%%_D%.lib copy /Y %SRC_DIR%\PCbuild\%BUILD_PATH%\python3%THREAD%%_D%.lib %PREFIX%\lib\
if errorlevel 1 exit 1
if exist %SRC_DIR%\PCbuild\%BUILD_PATH%\_tkinter%_D%.lib copy /Y %SRC_DIR%\PCbuild\%BUILD_PATH%\_tkinter%_D%.lib %PREFIX%\lib\
if errorlevel 1 exit 1


:: Populate the lib directory
del %PREFIX%\lib\libpython*.a
xcopy /s /y %SRC_DIR%\lib %PREFIX%\lib\python\
if errorlevel 1 exit 1

:: Copy venv[w]launcher scripts to venv\scripts\nt
:: See https://github.com/python/cpython/blob/b4a316087c32d83e375087fd35fc511bc430ee8b/lib/python/venv/__init__.py#L334-L376
if exist %SRC_DIR%\PCbuild\%BUILD_PATH%\venvlauncher%THREAD%%_D%.exe (
  @rem We did copy pythonw.exe until 3.12 but starting with 3.13 we seem to need the latter. Should we omit the first?
  copy /Y %SRC_DIR%\PCbuild\%BUILD_PATH%\venvlauncher%THREAD%%_D%.exe %PREFIX%\lib\python\venv\scripts\nt\python.exe
  copy /Y %SRC_DIR%\PCbuild\%BUILD_PATH%\venvlauncher%THREAD%%_D%.exe %PREFIX%\lib\python\venv\scripts\nt\venvlauncher%THREAD%%_D%.exe
) else (
  echo "WARNING :: %SRC_DIR%\PCbuild\%BUILD_PATH%\venvlauncher%THREAD%%_D%.exe does not exist"
)

if exist %SRC_DIR%\PCbuild\%BUILD_PATH%\venvwlauncher%THREAD%%_D%.exe (
  @rem We did copy pythonw.exe until 3.12 but starting with 3.13 we seem to need the latter. Should we omit the first?
  copy /Y %SRC_DIR%\PCbuild\%BUILD_PATH%\venvwlauncher%THREAD%%_D%.exe %PREFIX%\lib\python\venv\scripts\nt\pythonw.exe
  copy /Y %SRC_DIR%\PCbuild\%BUILD_PATH%\venvwlauncher%THREAD%%_D%.exe %PREFIX%\lib\python\venv\scripts\nt\venvwlauncher%THREAD%%_D%.exe
) else (
  echo "WARNING :: %SRC_DIR%\PCbuild\%BUILD_PATH%\venvwlauncher%THREAD%%_D%.exe does not exist"
)

:: Remove test data to save space.
:: Though keep `support` as some things use that.
mkdir %PREFIX%\lib\python\test_keep
if errorlevel 1 exit 1
move %PREFIX%\lib\python\test\__init__.py %PREFIX%\lib\python\test_keep\
if errorlevel 1 exit 1
move %PREFIX%\lib\python\test\support %PREFIX%\lib\python\test_keep\
if errorlevel 1 exit 1
rd /s /q %PREFIX%\lib\python\test
if errorlevel 1 exit 1
move %PREFIX%\lib\python\test_keep %PREFIX%\lib\python\test
if errorlevel 1 exit 1

:: We need our Python to be found!
if "%_D%" neq "" copy %PREFIX%\python%_D%.exe %PREFIX%\python.exe
if "%EXE_T%" neq "" copy %PREFIX%\python%EXE_T%.exe %PREFIX%\python.exe

set "PYTHON=%PREFIX%\python.exe"
:: bytecode compile the standard library
%PYTHON% -Wi %PREFIX%\lib\python\compileall.py -f -q -x "bad_coding|badsyntax|py2_" %PREFIX%\lib\python
if errorlevel 1 exit 1

:: Ensure that scripts are generated
:: https://github.com/conda-forge/python-feedstock/issues/384
%PYTHON% %RECIPE_DIR%\fix_staged_scripts.py
if errorlevel 1 exit 1

:: Some quick tests for common failures
echo "Testing print() does not print: Hello"
%PREFIX%\python.exe -c "print()" 2>&1 | findstr /r /c:"Hello"
if %errorlevel% neq 1 exit /b 1

echo "Testing print('Hello') prints: Hello"
%PREFIX%\python.exe "print('Hello')" 2>&1 | findstr /r /c:"Hello"
if %errorlevel% neq 0 exit /b 1

echo "Testing import of os (no DLL needed) does not print: The specified module could not be found"
%PREFIX%\python.exe -v -c "import os" 2>&1
%PREFIX%\python.exe -v -c "import os" 2>&1 | findstr /r /c:"The specified module could not be found"
if %errorlevel% neq 1 exit /b 1

echo "Testing import of %%m (DLL located via PATH needed) does not print: The specified module could not be found"
:: The names are our unvendored modules mapped to ...\DLLs\X.pyd
:: missing: libffi, expat, zlib(-ng)

:: Also %errorlevel% will not be updated round the loop so use && to
:: catch a successfull findstr, ie. a failure to load the underlying DLL
for %%m in (_ssl _sqlite3 _bz2 _tkinter _lzma _decimal _zstd) do (
   %PREFIX%\python.exe -c "import %%m" 2>&1 | findstr /r /c:"The specified module could not be found" && (
      %PREFIX%\python.exe -v -c "import %%m"
      exit /b 1
   )
)

echo build_base complete!
