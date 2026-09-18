@echo off
setlocal

set RUNTIME=C:\TEMP\_runtime
set SCRIPT_DIR=%~dp0
set "ISCC_PATH=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
set "SETUP_FILE=%SCRIPT_DIR%setup.iss"

set /p APP_VERSION=<"%SCRIPT_DIR%version.txt"
powershell.exe -NoProfile -Command "$expected = 'AppVersion=' + $env:APP_VERSION; if (-not (Get-Content -LiteralPath $env:SETUP_FILE | Where-Object { $_ -eq $expected })) { exit 1 }" >nul
if errorlevel 1 (
  echo ERRORE: version.txt e AppVersion in setup.iss non coincidono.
  pause
  exit /b 1
)

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
if not exist "%SCRIPT_DIR%dist\MyWayTools\MyWayTools.exe" (
  echo ERRORE: MyWayTools.exe non e' stato generato o e' stato bloccato dall'antivirus.
  echo Controlla la cronologia protezione di Windows Defender e riprova.
  pause
  exit /b 1
)

echo [3/4] Copia _runtime nella dist...
xcopy /E /I /Y "%RUNTIME%" "%SCRIPT_DIR%dist\MyWayTools\_runtime\"
if errorlevel 1 ( echo ERRORE: xcopy fallito & pause & exit /b 1 )

echo [4/4] Compilazione installer Inno Setup...
"%ISCC_PATH%" "%SCRIPT_DIR%setup.iss"
if errorlevel 1 ( echo ERRORE: Inno Setup fallito & pause & exit /b 1 )

echo BUILD COMPLETATO CON SUCCESSO
pause
