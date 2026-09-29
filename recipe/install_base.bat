setlocal EnableDelayedExpansion
echo on

if "%ARCH%"=="arm64" (set BUILD_PATH=arm64) else if "%ARCH%"=="64" (set BUILD_PATH=amd64) else (set BUILD_PATH=win32)
for /F "tokens=1,2 delims=." %%i in ("%PKG_VERSION%") do (
  set "VERNODOTS=%%i%%j"
  set "VER=%%i.%%j"
)
if "%PY_INTERP_DEBUG%"=="yes" (set _D=_d) else (set _D=)
if "%PY_GIL_DISABLED%"=="yes" (set "THREAD=t" & set "EXE_T=%VER%t") else (set "THREAD=" & set "EXE_T=")

for %%x in (python%VERNODOTS%%THREAD%%_D%.dll python3%THREAD%%_D%.dll python%EXE_T%%_D%.exe pythonw%EXE_T%%_D%.exe) do (
  if exist %SRC_DIR%\PCbuild\%BUILD_PATH%\%%x (
    copy /Y %SRC_DIR%\PCbuild\%BUILD_PATH%\%%x %PREFIX%
  ) else (
    echo "WARNING :: %SRC_DIR%\PCbuild\%BUILD_PATH%\%%x does not exist"
  )
)
for %%x in (python%_D%.pdb python%VERNODOTS%%_D%.pdb pythonw%_D%.pdb) do (
  if exist %SRC_DIR%\PCbuild\%BUILD_PATH%\%%x (
    copy /Y %SRC_DIR%\PCbuild\%BUILD_PATH%\%%x %PREFIX%
  ) else (
    echo "WARNING :: %SRC_DIR%\PCbuild\%BUILD_PATH%\%%x does not exist"
  )
)

copy %SRC_DIR%\LICENSE %PREFIX%\LICENSE_PYTHON.txt
if errorlevel 1 exit 1
mkdir %PREFIX%\DLLs
xcopy /s /y %SRC_DIR%\PCBuild\%BUILD_PATH%\*.pyd %PREFIX%\DLLs\
if errorlevel 1 exit 1
copy /Y %SRC_DIR%\PC\icons\py.ico %PREFIX%\DLLs\
if errorlevel 1 exit 1
copy /Y %SRC_DIR%\PC\icons\pyc.ico %PREFIX%\DLLs\
if errorlevel 1 exit 1

mkdir %PREFIX%\Tools
xcopy /s /y /i %SRC_DIR%\Tools\i18n %PREFIX%\Tools\i18n
if errorlevel 1 exit 1
xcopy /s /y /i %SRC_DIR%\Tools\scripts %PREFIX%\Tools\scripts
if errorlevel 1 exit 1
del %PREFIX%\Tools\scripts\README
if errorlevel 1 exit 1
del %PREFIX%\Tools\scripts\idle3
if errorlevel 1 exit 1
move /y %PREFIX%\Tools\scripts\pydoc3 %PREFIX%\Tools\scripts\pydoc3.py
if errorlevel 1 exit 1

xcopy /s /y %SRC_DIR%\Include %PREFIX%\include\
if errorlevel 1 exit 1
copy /Y %SRC_DIR%\PC\pyconfig.h %PREFIX%\include\
if errorlevel 1 exit 1
if not exist %SCRIPTS% (mkdir %SCRIPTS%)
if errorlevel 1 exit 1
for %%x in (idle pydoc) do (
    copy /Y %SRC_DIR%\Tools\scripts\%%x3 %SCRIPTS%\%%x
    if errorlevel 1 exit 1
)

if not exist %PREFIX%\libs mkdir %PREFIX%\libs
if exist %SRC_DIR%\PCbuild\%BUILD_PATH%\python%VERNODOTS%%THREAD%%_D%.lib copy /Y %SRC_DIR%\PCbuild\%BUILD_PATH%\python%VERNODOTS%%THREAD%%_D%.lib %PREFIX%\libs\
if errorlevel 1 exit 1
if exist %SRC_DIR%\PCbuild\%BUILD_PATH%\python3%THREAD%%_D%.lib copy /Y %SRC_DIR%\PCbuild\%BUILD_PATH%\python3%THREAD%%_D%.lib %PREFIX%\libs\
if errorlevel 1 exit 1
if exist %SRC_DIR%\PCbuild\%BUILD_PATH%\_tkinter%_D%.lib copy /Y %SRC_DIR%\PCbuild\%BUILD_PATH%\_tkinter%_D%.lib %PREFIX%\libs\
if errorlevel 1 exit 1
del %PREFIX%\libs\libpython*.a
xcopy /s /y %SRC_DIR%\Lib %PREFIX%\Lib\
if errorlevel 1 exit 1

if exist %SRC_DIR%\PCbuild\%BUILD_PATH%\venvlauncher%THREAD%%_D%.exe (
  copy /Y %SRC_DIR%\PCbuild\%BUILD_PATH%\venvlauncher%THREAD%%_D%.exe %PREFIX%\Lib\venv\scripts\nt\python.exe
  copy /Y %SRC_DIR%\PCbuild\%BUILD_PATH%\venvlauncher%THREAD%%_D%.exe %PREFIX%\Lib\venv\scripts\nt\venvlauncher%THREAD%%_D%.exe
) else (
  echo "WARNING :: %SRC_DIR%\PCbuild\%BUILD_PATH%\venvlauncher%THREAD%%_D%.exe does not exist"
)
if exist %SRC_DIR%\PCbuild\%BUILD_PATH%\venvwlauncher%THREAD%%_D%.exe (
  copy /Y %SRC_DIR%\PCbuild\%BUILD_PATH%\venvwlauncher%THREAD%%_D%.exe %PREFIX%\Lib\venv\scripts\nt\pythonw.exe
  copy /Y %SRC_DIR%\PCbuild\%BUILD_PATH%\venvwlauncher%THREAD%%_D%.exe %PREFIX%\Lib\venv\scripts\nt\venvwlauncher%THREAD%%_D%.exe
) else (
  echo "WARNING :: %SRC_DIR%\PCbuild\%BUILD_PATH%\venvwlauncher%THREAD%%_D%.exe does not exist"
)

mkdir %PREFIX%\Lib\test_keep
if errorlevel 1 exit 1
move %PREFIX%\Lib\test\__init__.py %PREFIX%\Lib\test_keep\
if errorlevel 1 exit 1
move %PREFIX%\Lib\test\support %PREFIX%\Lib\test_keep\
if errorlevel 1 exit 1
rd /s /q %PREFIX%\Lib\test
if errorlevel 1 exit 1
move %PREFIX%\Lib\test_keep %PREFIX%\Lib\test
if errorlevel 1 exit 1

if "%_D%" neq "" copy %PREFIX%\python%_D%.exe %PREFIX%\python.exe
if "%EXE_T%" neq "" copy %PREFIX%\python%EXE_T%.exe %PREFIX%\python.exe
%PREFIX%\python.exe -Wi %PREFIX%\Lib\compileall.py -f -q -x "bad_coding|badsyntax|py2_" %PREFIX%\Lib
if errorlevel 1 exit 1
%PREFIX%\python.exe %RECIPE_DIR%\fix_staged_scripts.py
if errorlevel 1 exit 1

echo "Testing print() does not print: Hello"
%CONDA_EXE% run -p %PREFIX% cd %PREFIX% & %PREFIX%\python.exe -c "print()" 2>&1 | findstr /r /c:"Hello"
if %errorlevel% neq 1 exit /b 1
echo "Testing print('Hello') prints: Hello"
%CONDA_EXE% run -p %PREFIX% cd %PREFIX% & %PREFIX%\python.exe "print('Hello')" 2>&1 | findstr /r /c:"Hello"
if %errorlevel% neq 0 exit /b 1
echo "Testing import of os (no DLL needed) does not print: The specified module could not be found"
%CONDA_EXE% run -p %PREFIX% cd %PREFIX% & %PREFIX%\python.exe -v -c "import os" 2>&1
%CONDA_EXE% run -p %PREFIX% cd %PREFIX% & %PREFIX%\python.exe -v -c "import os" 2>&1 | findstr /r /c:"The specified module could not be found"
if %errorlevel% neq 1 exit /b 1
echo "Testing import of %%m (DLL located via PATH needed) does not print: The specified module could not be found"
for %%m in (_ssl _sqlite3 _bz2 _tkinter _lzma _decimal _zstd) do (
   %CONDA_EXE% run -p %PREFIX% cd %PREFIX% & %PREFIX%\python.exe -c "import %%m" 2>&1 | findstr /r /c:"The specified module could not be found" && (
      %CONDA_EXE% run -p %PREFIX% cd %PREFIX% & %PREFIX%\python.exe -v -c "import %%m"
      exit /b 1
   )
)
echo install_base complete!
