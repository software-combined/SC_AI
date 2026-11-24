#define ResourcesDir "@RESOURCES@"
#define OutputDir "@OUTPUT@"
#define ProductVersion "@VERSION@"

[Setup]
AppId=SCG.Router.Installer
AppName=SCG Router
AppVersion={#ProductVersion}
DefaultDirName={localappdata}\Programs\SCG Router Installer
DefaultGroupName=SCG Router
PrivilegesRequired=lowest
OutputDir={#OutputDir}
OutputBaseFilename=SCG-Router-Installer-{#ProductVersion}-Windows
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
DisableStartupPrompt=yes
SetupIconFile=@ICON@
; Microsoft's licence requires users to accept terms protecting its runtime files.
LicenseFile=@TERMS@
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableReadyPage=yes
DisableFinishedPage=yes
Uninstallable=no

[Files]
; Keep the probe in front of the solid-compressed runtime.
Source: "@REPEAT_PROBE@"; Flags: dontcopy
Source: "@REPEAT_INVENTORY@"; Flags: dontcopy
Source: "@REPEAT_ICON@"; Flags: dontcopy
Source: "{#ResourcesDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\Install SCG Router"; Filename: "{app}\runtime\python\pythonw.exe"; Parameters: """{app}\router\packaging\native_setup.py"" --resources ""{app}"" --action install"

[Run]
Filename: "{app}\runtime\python\pythonw.exe"; Parameters: """{app}\router\packaging\native_setup.py"" --resources ""{app}"" --action install"; Description: "Set up SCG Router"; Flags: postinstall skipifsilent

[Code]
function InitializeSetup: Boolean;
var
  Code: Integer;
  Folder: String;
begin
  Result := True;
  if WizardSilent or (ParamCount > 0) then
    Exit;
  try
    ExtractTemporaryFile('repeat-menu.exe');
    ExtractTemporaryFile('repeat-files.txt');
    ExtractTemporaryFile('repeat-icon.png');
    Folder := ExpandConstant('{tmp}');
    if Exec(Folder + '\repeat-menu.exe', '--repeat "' + Folder + '\repeat-files.txt" "' +
      Folder + '\repeat-icon.png"', Folder, SW_SHOWNORMAL, ewWaitUntilTerminated, Code) then
      Result := Code <> 0;
  except
    Log('SCG Router repeat check was unavailable.');
  end;
end;

procedure InitializeWizard;
begin
  WizardForm.Caption := 'SCG Router';
end;
