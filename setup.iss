; setup.iss

[Setup]
AppName=MyWay Tools
AppVersion=1.0.16
AppPublisher=Andrea
DefaultDirName={pf}\MyWayTools
DefaultGroupName=MyWay Tools
OutputDir={#SourcePath}\installer_output
OutputBaseFilename=setup
Compression=lzma2
SolidCompression=yes
CloseApplications=yes
RestartApplications=no
; Se hai un'icona:
SetupIconFile=logo.ico
PrivilegesRequired=admin

[Files]
; Copia tutta la cartella compilata da PyInstaller
Source: "dist\MyWayTools\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Collegamento nel menu Start
Name: "{group}\MyWay Tools"; Filename: "{app}\MyWayTools.exe"
; Collegamento sul desktop
Name: "{commondesktop}\MyWay Tools"; Filename: "{app}\MyWayTools.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Crea collegamento sul desktop"; GroupDescription: "Opzioni aggiuntive:"

[Run]
; Avvia il programma alla fine dell'installazione (solo se non è un update silenzioso)
Filename: "{app}\MyWayTools.exe"; Flags: nowait postinstall skipifsilent

[Code]
// Questo blocco fa sì che durante un update silenzioso
// l'app venga chiusa prima di sovrascrivere i file
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
  begin
    // nulla da fare, CloseApplications=yes pensa a tutto
  end;
end;