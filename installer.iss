; Script adapted for automated building via GitHub Actions

#define MyAppName "Vinyller"
#define MyAppPublisher "Maxim Moshkin"
#define MyAppURL "https://github.com/maxcreations/vinyller"
#define MyAppExeName "Vinyller.exe"

[Setup]
; IMPORTANT: Unique AppId. Do not change it!
AppId={{DBE5AA4E-1507-4518-820F-8EF4F5BBE623}
AppName={#MyAppName}

; Version is specified directly so that the update_version.py script can update it during release
AppVersion=1.1.0

AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}

; Restrictions and optimization for 64-bit systems
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
PrivilegesRequiredOverridesAllowed=dialog

; Output settings (adapted for GitHub Actions)
OutputDir=dist
OutputBaseFilename=Vinyller_Windows_Setup
SetupIconFile=assets\logo\app_icon_win.ico
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "french"; MessagesFile: "compiler:Languages\French.isl"
Name: "german"; MessagesFile: "compiler:Languages\German.isl"
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl"
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"
Name: "polish"; MessagesFile: "compiler:Languages\Polish.isl"
Name: "portuguese"; MessagesFile: "compiler:Languages\Portuguese.isl"
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "swedish"; MessagesFile: "compiler:Languages\Swedish.isl"
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Taking files from the build folder dist\Vinyller (case-sensitive as per build.yml)
Source: "dist\Vinyller\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\Vinyller\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent