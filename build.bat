@echo off
setlocal

set RUNTIME=C:\TEMP\_runtime
set SCRIPT_DIR=%~dp0
set "PERF_DIR=%SCRIPT_DIR%scripts\BUSINESS\15_PERFORMANCE_MANAGEMENT_CRM"
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

echo [1/5] Installazione dipendenze nel runtime...
"%RUNTIME%\python.exe" -m pip install -r "%SCRIPT_DIR%requirements_runtime.txt" --no-warn-script-location
if errorlevel 1 ( echo ERRORE: pip fallito & pause & exit /b 1 )

echo [2/5] Preparazione MJML per Performance Management CRM...
if not exist "%PERF_DIR%\node_modules\mjml\bin\mjml" (
  call npm.cmd ci --prefix "%PERF_DIR%"
  if errorlevel 1 ( echo ERRORE: npm ci fallito & pause & exit /b 1 )
)
set "NODE_EXE="
for /f "delims=" %%I in ('where node 2^>nul') do if not defined NODE_EXE set "NODE_EXE=%%I"
if not defined NODE_EXE (
  echo ERRORE: Node.js non trovato. Installare Node.js LTS per creare l'installer.
  pause
  exit /b 1
)

echo [3/5] Build con PyInstaller...
"%RUNTIME%\python.exe" -m PyInstaller "%SCRIPT_DIR%Menu.spec" --clean -y
if errorlevel 1 ( echo ERRORE: PyInstaller fallito & pause & exit /b 1 )
if not exist "%SCRIPT_DIR%dist\MyWayTools\MyWayTools.exe" (
  echo ERRORE: MyWayTools.exe non e' stato generato o e' stato bloccato dall'antivirus.
  echo Controlla la cronologia protezione di Windows Defender e riprova.
  pause
  exit /b 1
)

echo [4/5] Copia runtime Python e MJML nella dist...
xcopy /E /I /Y "%RUNTIME%" "%SCRIPT_DIR%dist\MyWayTools\_runtime\"
if errorlevel 1 ( echo ERRORE: xcopy fallito & pause & exit /b 1 )
set "PERF_DIST=%SCRIPT_DIR%dist\MyWayTools\_internal\scripts\BUSINESS\15_PERFORMANCE_MANAGEMENT_CRM"
xcopy /E /I /Y "%PERF_DIR%\node_modules" "%PERF_DIST%\node_modules\"
if errorlevel 1 ( echo ERRORE: copia moduli MJML fallita & pause & exit /b 1 )
copy /Y "%NODE_EXE%" "%PERF_DIST%\node.exe" >nul
if errorlevel 1 ( echo ERRORE: copia Node.js fallita & pause & exit /b 1 )

echo [5/5] Compilazione installer Inno Setup...
"%ISCC_PATH%" "%SCRIPT_DIR%setup.iss"
if errorlevel 1 ( echo ERRORE: Inno Setup fallito & pause & exit /b 1 )

echo BUILD COMPLETATO CON SUCCESSO
pause
