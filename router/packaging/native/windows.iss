#define ResourcesDir "@RESOURCES@"
#define OutputDir "@OUTPUT@"
#define ProductVersion "@VERSION@"

[Setup]
AppId=SCG.Router.Installer
AppName=SCG Router
AppVersion={#ProductVersion}
; Old installer files must not enter a new version's retained payload.
DefaultDirName={localappdata}\Programs\SCG Router Installer\{#ProductVersion}@SUFFIX@
UsePreviousAppDir=no
DefaultGroupName=SCG Router
PrivilegesRequired=lowest
OutputDir={#OutputDir}
OutputBaseFilename=SCG-Router-Installer-{#ProductVersion}-Windows@SUFFIX@
@ARCHITECTURES@
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
function SetEnvironmentVariable(lpName, lpValue: String): Boolean;
  external 'SetEnvironmentVariableW@kernel32.dll stdcall';

function InitializeSetup: Boolean;
var
  Code: Integer;
  Folder, PreviousExtract: String;
begin
  Result := True;
  if WizardSilent or (ParamCount > 0) then
    Exit;
  try
    ExtractTemporaryFile('repeat-menu.exe');
    ExtractTemporaryFile('repeat-files.txt');
    ExtractTemporaryFile('repeat-icon.png');
    Folder := ExpandConstant('{tmp}');
    PreviousExtract := GetEnv('DOTNET_BUNDLE_EXTRACT_BASE_DIR');
    if not SetEnvironmentVariable('DOTNET_BUNDLE_EXTRACT_BASE_DIR', Folder) then
      Exit;
    try
      if Exec(Folder + '\repeat-menu.exe', '--repeat "' + Folder + '\repeat-files.txt" "' +
        Folder + '\repeat-icon.png"', Folder, SW_SHOWNORMAL, ewWaitUntilTerminated, Code) then
        Result := Code <> 0;
    finally
      SetEnvironmentVariable('DOTNET_BUNDLE_EXTRACT_BASE_DIR', PreviousExtract);
    end;
  except
    Log('SCG Router repeat check was unavailable.');
  end;
end;

procedure InitializeWizard;
begin
  WizardForm.Caption := 'SCG Router';
end;
