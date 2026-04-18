; Inno Setup script for Zündpunkt
; -----------------------------------------------------------------------------
; Build the PyInstaller bundle first (pyinstaller Zundpunkt.spec), then compile
; this script with:
;   ISCC.exe /DAppVersion=0.2.0 installer\Zundpunkt.iss
; The build.ps1 wrapper reads version.py and passes /DAppVersion automatically.
; -----------------------------------------------------------------------------

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

#define AppName         "Zundpunkt"
#define AppDisplayName  "Zündpunkt"
#define AppPublisher    "Nathan Ladd"
#define AppURL          "https://github.com/nathanladd/Zundpunkt"
#define AppExeName      "Zundpunkt.exe"

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
OutputBaseFilename=Zundpunkt-Setup-{#AppVersion}
#if FileExists(AddBackslash(SourcePath) + "zundpunkt.ico")
SetupIconFile={#SourcePath}\zundpunkt.ico
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
; If Zundpunkt.exe is running during install/uninstall, Inno Setup checks for
; this named mutex and offers to close the running instance (and restart it
; after the upgrade when possible). The instructor app creates the mutex at
; startup — see instructor/main.py _acquire_singleton_mutex.
AppMutex=ZundpunktSingletonMutex
CloseApplications=yes
RestartApplications=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "firewall";    Description: "Allow {#AppDisplayName} through the Windows firewall (port 5000)"; GroupDescription: "Networking:"; Flags: unchecked

[Files]
; Entire PyInstaller one-dir bundle (dist/Zundpunkt/*) goes into {app}.
Source: "..\dist\Zundpunkt\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\{#AppDisplayName}"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppDisplayName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
; Best-effort firewall rule so the student LAN can reach the server.
Filename: "netsh.exe"; Parameters: "advfirewall firewall add rule name=""{#AppDisplayName}"" dir=in action=allow protocol=TCP localport=5000"; Flags: runhidden; Tasks: firewall
; Offer to launch the app at the end of install.
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#AppDisplayName}}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "netsh.exe"; Parameters: "advfirewall firewall delete rule name=""{#AppDisplayName}"""; Flags: runhidden; RunOnceId: "RemoveFirewallRule"

[UninstallDelete]
; %LOCALAPPDATA%\Zundpunkt holds the DB, uploaded media, and backups. Leave
; it alone by default so a reinstall/upgrade keeps question content, and let
; the user decide what to purge via a dedicated prompt below.
Type: filesandordirs; Name: "{app}"

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  UserData: String;
begin
  if CurUninstallStep = usPostUninstall then begin
    UserData := ExpandConstant('{localappdata}\Zundpunkt');
    if DirExists(UserData) then begin
      if MsgBox(
            'Also delete Zündpunkt user data (question database, uploaded images, backups)?' + Chr(13) + Chr(10) +
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
