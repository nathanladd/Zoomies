; Inno Setup script for Rudi
; -----------------------------------------------------------------------------
; Build the PyInstaller bundle first (pyinstaller Rudi.spec), then compile
; this script with:
;   ISCC.exe /DAppVersion=0.2.0 installer\Rudi.iss
; The build.ps1 wrapper reads version.py and passes /DAppVersion automatically.
; -----------------------------------------------------------------------------

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

#define AppName         "Rudi"
#define AppDisplayName  "Rudi"
#define AppPublisher    "Nathan Ladd"
#define AppURL          "https://github.com/nathanladd/Zundpunkt"
#define AppExeName      "Rudi.exe"

[Setup]
AppId={{7A5E3FB2-2C6E-4E4A-9CBF-9D3D5F44A4A8}
AppName={#AppDisplayName}
AppVersion={#AppVersion}
AppVerName={#AppDisplayName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppDisplayName}
DisableProgramGroupPage=yes
OutputDir=..\dist\installer
OutputBaseFilename=Rudi-Setup-{#AppVersion}
#if FileExists(AddBackslash(SourcePath) + "Rudi_App_Icon.ico")
SetupIconFile={#SourcePath}\Rudi_App_Icon.ico
#endif
UninstallDisplayIcon={app}\{#AppExeName}
Compression=lzma2/ultra
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog
; If Rudi.exe is running during install/uninstall, Inno Setup checks for
; this named mutex and offers to close the running instance (and restart it
; after the upgrade when possible). The instructor app creates the mutex at
; startup — see instructor/main.py _acquire_singleton_mutex.
AppMutex=RudiSingletonMutex
CloseApplications=yes
RestartApplications=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Entire PyInstaller one-dir bundle (dist/Rudi/*) goes into {app}.
Source: "..\dist\Rudi\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\{#AppDisplayName}"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppDisplayName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
; Offer to launch the app at the end of install.
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#AppDisplayName}}"; Flags: nowait postinstall skipifsilent


[UninstallDelete]
; %LOCALAPPDATA%\Rudi holds the DB, uploaded media, and backups. Leave
; it alone by default so a reinstall/upgrade keeps question content, and let
; the user decide what to purge via a dedicated prompt below.
Type: filesandordirs; Name: "{app}"

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  UserData: String;
begin
  if CurUninstallStep = usPostUninstall then begin
    UserData := ExpandConstant('{localappdata}\Rudi');
    if DirExists(UserData) then begin
      if MsgBox(
            'Also delete Rudi user data (question database, uploaded images, backups)?' + Chr(13) + Chr(10) +
            Chr(13) + Chr(10) +
            UserData + Chr(13) + Chr(10) +
            Chr(13) + Chr(10) +
            'Choose No to keep your content for a future reinstall.',
            mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then begin
        DelTree(UserData, True, True, True);
      end;
    end;
  end;
end;
