; Скрипт адаптирован для автосборки через GitHub Actions

#define MyAppName "Vinyller"
#define MyAppPublisher "Maxim Moshkin"
#define MyAppURL "https://github.com/maxcreations/vinyller"
#define MyAppExeName "Vinyller.exe"

[Setup]
; ВАЖНО: Уникальный AppId для вашего проекта. Больше его не меняйте!
AppId={{DBE5AA4E-1507-4518-820F-8EF4F5BBE623}
AppName={#MyAppName}

; Версия указана напрямую, чтобы скрипт update_version.py мог ее обновлять при релизе
AppVersion=1.0.0

AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}

; Ограничения и оптимизация для 64-битных систем
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
PrivilegesRequiredOverridesAllowed=dialog

; Настройки вывода (адаптировано под GitHub Actions)
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
; Берем файлы из папки сборки dist\Vinyller (с учетом регистра из build.yml)
Source: "dist\Vinyller\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\Vinyller\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent