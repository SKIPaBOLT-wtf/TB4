#ifndef ROLE
  #error ROLE is required
#endif
#ifndef SourceDir
  #error SourceDir is required
#endif
#ifndef OutputDir
  #error OutputDir is required
#endif
#ifndef Version
  #define Version "0.0.1"
#endif
#if ROLE != "watchdog" && ROLE != "fetcher"
  #error Invalid role
#endif

[Setup]
AppId=TB4.{#ROLE}.desktop
AppName=TB4 {#ROLE}
AppVersion={#Version}
DefaultDirName={localappdata}\Programs\TB4\{#ROLE}
DefaultGroupName=TB4 {#ROLE}
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutputDir}
OutputBaseFilename=TB4-{#ROLE}-{#Version}-windows-x64-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=no
RestartApplications=no
UninstallDisplayIcon={app}\tb4-{#ROLE}.exe
DisableProgramGroupPage=yes

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{userprograms}\TB4 {#ROLE}"; Filename: "{app}\tb4-{#ROLE}.exe"

[Tasks]
Name: "autostart"; Description: "Open this role's tray app when I sign in"; Flags: unchecked

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "TB4.{#ROLE}.desktop"; ValueData: """{app}\tb4-{#ROLE}.exe"""; Tasks: autostart; Flags: uninsdeletevalue

[Run]
Filename: "{app}\tb4-{#ROLE}.exe"; Description: "Open TB4 {#ROLE} configuration"; Flags: nowait postinstall skipifsilent unchecked

[Code]
function RoleIsStopped(): Boolean;
var
  ExitCode: Integer;
  Worker: String;
begin
  Worker := ExpandConstant('{app}\tb4-{#ROLE}-worker.exe');
  Result := True;
  if FileExists(Worker) then
  begin
    Result := Exec(Worker, '--action probe-lock', '', SW_HIDE, ewWaitUntilTerminated, ExitCode);
    if Result then Result := ExitCode = 0;
  end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  if not RoleIsStopped() then
    Result := 'Stop this TB4 role safely and exit its tray application before upgrading. The other role is not affected.';
end;

function InitializeUninstall(): Boolean;
begin
  Result := RoleIsStopped();
  if not Result then
    MsgBox('Stop this TB4 role safely and exit its tray application before uninstalling. Private configuration will be preserved.', mbError, MB_OK);
end;
