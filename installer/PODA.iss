#define AppName "PODA"
#define AppVersion "1.0.0"
#define AppPublisher "Codex"
#define AppExeName "PODA.exe"
#define OracleUser "DIGITALIZACION"
#define OracleTargets "172.16.60.21:1521:PRDSGH2"
#define OracleJdbcJar "jdbc/ojdbc8.jar"
#define OracleOwner "DIGITALIZACION"
#define OracleSourceTable "DIGITALIZACION"

[Setup]
AppId={{C5EDEB0B-4B78-4ED2-8B76-7D7B46F4E6A1}}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
OutputDir=..\installer_output
OutputBaseFilename=PODA_Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Files]
Source: "..\dist\PODA\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{commondesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Crear icono en el escritorio"; GroupDescription: "Iconos adicionales:"

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Ejecutar {#AppName}"; Flags: nowait postinstall skipifsilent

[Code]
procedure EnsureOracleConfig;
var
  ConfigDir: string;
  ConfigFile: string;
  Content: string;
begin
  ConfigDir := AddBackslash(ExpandConstant('{userappdata}')) + '{#AppName}';
  ConfigFile := AddBackslash(ConfigDir) + '.env';

  if not FileExists(ConfigFile) then
  begin
    ForceDirectories(ConfigDir);
    Content :=
      '# Oracle credentials and connection' + #13#10 +
      'ORACLE_USER={#OracleUser}' + #13#10 +
      'ORACLE_PASSWORD=' + #13#10 +
      'ORACLE_TARGETS={#OracleTargets}' + #13#10 +
      'ORACLE_JDBC_JAR={#OracleJdbcJar}' + #13#10#13#10 +
      '# Optional schema/table overrides' + #13#10 +
      'ORACLE_OWNER={#OracleOwner}' + #13#10 +
      'ORACLE_SOURCE_TABLE={#OracleSourceTable}' + #13#10;
    SaveStringToFile(ConfigFile, Content, False);
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    EnsureOracleConfig;
end;
