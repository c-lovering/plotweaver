; Inno Setup script for the Plotweaver installer.
; Build dist\Plotweaver with PyInstaller and the sample project first, then:
;   python make_sample.py "build\Sample Project" --replace
;   ISCC.exe /DMyAppVersion=0.4.0 packaging\windows\installer.iss
; Output: dist\Plotweaver-<version>-Setup.exe
;
; Installs per-user by default (no admin prompt, into %LOCALAPPDATA%\Programs\Plotweaver);
; the setup offers "install for all users" if you want Program Files instead.
;
; The sample project goes to Documents\Plotweaver\Sample Project. It's installed when that
; folder doesn't exist yet. If it holds a sample from an older version, setup offers (ticked)
; to replace it; a sample from this version or newer, or a folder of the user's own with that
; name, is never touched. Uninstalling leaves it alone, since people may have edited it.

#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif
#define MyAppName "Plotweaver"
#define MyAppExe "Plotweaver.exe"

[Setup]
AppId={{6E0F7B52-3A4C-4F7E-9C1D-8B2A5E6F0D13}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher=sierrax
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\..\dist
OutputBaseFilename={#MyAppName}-{#MyAppVersion}-Setup
SetupIconFile=plotweaver.ico
UninstallDisplayIcon={app}\{#MyAppExe}
UninstallDisplayName={#MyAppName}
LicenseFile=..\..\LICENSE
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; the sample project goes in the installing user's Documents even for all-users installs
UsedUserAreasWarning=no

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "replacesample"; Description: "Replace my older Sample Project in Documents\Plotweaver with this version's (any changes I made to it will be lost)"; GroupDescription: "Sample project:"; Check: SampleIsOlder

[Files]
; Everything PyInstaller produced. (No portable.txt here, so settings go in the normal per-user place.)
Source: "..\..\dist\Plotweaver\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; The sample project (see the top of this file). Never uninstalled: it's the user's to keep.
Source: "..\..\build\Sample Project\*"; DestDir: "{userdocs}\Plotweaver\Sample Project"; Flags: ignoreversion recursesubdirs createallsubdirs uninsneveruninstall; Check: CopySample

[InstallDelete]
; clear out the previous version's libraries so an upgrade never mixes old and new files
Type: filesandordirs; Name: "{app}\_internal"
; an older sample the user chose to replace: remove it first so no stale notes are left behind
Type: filesandordirs; Name: "{userdocs}\Plotweaver\Sample Project"; Tasks: replacesample

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExe}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[Code]
var
  DoCopySample: Boolean;

function SampleDir: String;
begin
  Result := ExpandConstant('{userdocs}\Plotweaver\Sample Project');
end;

{ Version of Plotweaver that wrote the sample now in Documents ('' if none or not ours). }
function InstalledSampleVersion: String;
begin
  Result := GetIniString('sample', 'version', '', SampleDir + '\.plotweaver-sample');
end;

function SampleIsOlder: Boolean;
var
  OldV, NewV: Int64;
  S: String;
begin
  Result := False;
  S := Trim(InstalledSampleVersion);
  if S = '' then
    Exit;
  if StrToVersion(S, OldV) and StrToVersion('{#MyAppVersion}', NewV) then
    Result := ComparePackedVersion(OldV, NewV) < 0;
end;

{ Decide once, before anything is deleted or copied: the Check on [Files] runs per file,
  and the folder exists as soon as the first one lands. }
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
    DoCopySample := (not DirExists(SampleDir)) or
                    (SampleIsOlder and WizardIsTaskSelected('replacesample'));
end;

function CopySample: Boolean;
begin
  Result := DoCopySample;
end;
