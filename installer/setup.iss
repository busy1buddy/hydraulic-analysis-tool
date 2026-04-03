; Inno Setup Script for Hydraulic Analysis Tool
; Build with Inno Setup 6.x: https://jrsoftware.org/isinfo.php

[Setup]
AppName=Hydraulic Analysis Tool
AppVersion=1.0.0
AppPublisher=Hydraulic Engineering Tools
AppPublisherURL=https://github.com/hydraulic-tool
DefaultDirName={autopf}\HydraulicAnalysisTool
DefaultGroupName=Hydraulic Analysis Tool
OutputDir=..\dist
OutputBaseFilename=HydraulicAnalysisTool_Setup
Compression=lzma2/ultra64
SolidCompression=yes
SetupIconFile=
UninstallDisplayIcon={app}\HydraulicAnalysisTool.exe
WizardStyle=modern
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; Main application from PyInstaller output
Source: "..\dist\HydraulicAnalysisTool\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; Example model files
Source: "..\models\*.inp"; DestDir: "{app}\models"; Flags: ignoreversion

[Icons]
Name: "{group}\Hydraulic Analysis Tool"; Filename: "{app}\HydraulicAnalysisTool.exe"
Name: "{group}\Uninstall Hydraulic Analysis Tool"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Hydraulic Analysis Tool"; Filename: "{app}\HydraulicAnalysisTool.exe"; Tasks: desktopicon

[Registry]
; .hap file association
Root: HKCU; Subkey: "Software\Classes\.hap"; ValueType: string; ValueName: ""; ValueData: "HydraulicAnalysisTool.hap"; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\HydraulicAnalysisTool.hap"; ValueType: string; ValueName: ""; ValueData: "Hydraulic Analysis Project"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\HydraulicAnalysisTool.hap\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\HydraulicAnalysisTool.exe,0"
Root: HKCU; Subkey: "Software\Classes\HydraulicAnalysisTool.hap\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\HydraulicAnalysisTool.exe"" ""%1"""

; .inp file association
Root: HKCU; Subkey: "Software\Classes\.inp"; ValueType: string; ValueName: ""; ValueData: "HydraulicAnalysisTool.inp"; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\HydraulicAnalysisTool.inp"; ValueType: string; ValueName: ""; ValueData: "EPANET Network File"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\HydraulicAnalysisTool.inp\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\HydraulicAnalysisTool.exe,0"
Root: HKCU; Subkey: "Software\Classes\HydraulicAnalysisTool.inp\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\HydraulicAnalysisTool.exe"" ""%1"""

[Run]
Filename: "{app}\HydraulicAnalysisTool.exe"; Description: "Launch Hydraulic Analysis Tool"; Flags: nowait postinstall skipifsilent
