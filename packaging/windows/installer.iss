; Inno Setup script for the Plotweaver installer.
; Build dist\Plotweaver with PyInstaller first, then:
;   ISCC.exe /DMyAppVersion=0.4.0 packaging\windows\installer.iss
; Output: dist\Plotweaver-<version>-Setup.exe
;
; Installs per-user by default (no admin prompt, into %LOCALAPPDATA%\Programs\Plotweaver);
; the setup offers "install for all users" if you want Program Files instead.

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

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Everything PyInstaller produced. (No portable.txt here, so settings go in the normal per-user place.)
Source: "..\..\dist\Plotweaver\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; clear out the previous version's libraries so an upgrade never mixes old and new files
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExe}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
