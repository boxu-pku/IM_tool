#ifndef AppVersion
  #error Build through packaging/build_desktop.py
#endif
#define AppId "io.github.boxu_pku.IMTool"
[Setup]
AppId={#AppId}
AppName=IM Tool
AppVersion={#AppVersion}
AppPublisher=Bo Xu
DefaultDirName={localappdata}\Programs\IM Tool
DefaultGroupName=IM Tool
DisableProgramGroupPage=yes
DisableWelcomePage=no
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
ShowLanguageDialog=yes
WizardStyle=modern
WizardImageFile={#WizardArt}\welcome.bmp
WizardSmallImageFile={#WizardArt}\header.bmp
SetupIconFile=..\..\im_app\resources\im-tool.ico
UninstallDisplayIcon={app}\IMTool.exe
OutputDir={#Output}
OutputBaseFilename=IM-Tool-Setup-{#AppVersion}-x64
Compression=lzma2/fast
SolidCompression=yes

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "zhcn"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Messages]
en.WelcomeLabel2=Setup will install IM Tool on this computer for your Windows account.%n%nThe application includes a practice workspace and two offline manuals. On first launch, IM Tool creates a writable library in your user profile.
zhcn.WelcomeLabel2=安装向导将为当前 Windows 用户安装 IM Tool。%n%n软件包含练习工作区及中英文离线手册。首次启动时，程序会在用户目录中创建可写的工作材料库。

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#Bundle}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\IM Tool"; Filename: "{app}\IMTool.exe"; AppUserModelID: "{#AppId}"
Name: "{autodesktop}\IM Tool"; Filename: "{app}\IMTool.exe"; AppUserModelID: "{#AppId}"; Tasks: desktopicon

[Run]
Filename: "{app}\IMTool.exe"; Description: "{cm:LaunchProgram,IM Tool}"; Flags: nowait postinstall skipifsilent
