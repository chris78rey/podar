#define AppName "OrganizaPlanillas"
#define AppVersion "1.0.0"
#define AppPublisher "Codex"
#define AppExeName "OrganizaPlanillas.exe"

[Setup]
AppId={{B8F4F61F-0D10-4F32-8E0E-37B8D5EAA9B2}}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
OutputDir=..\installer_output
OutputBaseFilename=OrganizaPlanillas_Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Files]
Source: "..\dist\OrganizaPlanillas\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{commondesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Crear icono en el escritorio"; GroupDescription: "Iconos adicionales:"

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Ejecutar {#AppName}"; Flags: nowait postinstall skipifsilent
