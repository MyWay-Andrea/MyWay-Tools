@echo off
setlocal

set RUNTIME=C:\TEMP\_runtime
set SCRIPT_DIR=%~dp0
set "ISCC_PATH=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"

if not exist "%ISCC_PATH%" set "ISCC_PATH=%LocalAppData%\Programs\Inno Setup 6\ISCC.exe"
if not exist "%ISCC_PATH%" (
  echo ERRORE: Inno Setup 6 non trovato.
  echo Installa Inno Setup 6 o aggiorna il percorso in build.bat.
  pause
  exit /b 1
)

echo [1/4] Installazione dipendenze nel runtime...
"%RUNTIME%\python.exe" -m pip install -r "%SCRIPT_DIR%requirements_runtime.txt" --no-warn-script-location
if errorlevel 1 ( echo ERRORE: pip fallito & pause & exit /b 1 )

echo [2/4] Build con PyInstaller...
"%RUNTIME%\python.exe" -m PyInstaller "%SCRIPT_DIR%Menu.spec" --clean -y
if errorlevel 1 ( echo ERRORE: PyInstaller fallito & pause & exit /b 1 )

echo [3/4] Copia _runtime nella dist...
xcopy /E /I /Y "%RUNTIME%" "%SCRIPT_DIR%dist\MyWayTools\_runtime\"
if errorlevel 1 ( echo ERRORE: xcopy fallito & pause & exit /b 1 )

echo [4/4] Compilazione installer Inno Setup...
"%ISCC_PATH%" "%SCRIPT_DIR%setup.iss"
if errorlevel 1 ( echo ERRORE: Inno Setup fallito & pause & exit /b 1 )

echo BUILD COMPLETATO CON SUCCESSO
pause
