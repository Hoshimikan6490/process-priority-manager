"""Build the MSI.

pyappdist builds the app image and a base .wxs; this script customises the .wxs
(install scope, install folder, update-check feature, UI) and compiles it together
with installer/UI.wxs using the WiX CLI.
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INSTALLER = ROOT / "installer"
TARGET = "windowsmsi"
BUILD = ROOT / ".appdist-build" / TARGET
BASE_WXS = BUILD / "process-priority-manager.wxs"
CUSTOM_WXS = BUILD / "ppm.wxs"
OUT_DIR = ROOT / "appdist" / TARGET / "dist"

# The app reads this key (see src/config_manager.py) to honour the installer choice.
REG_KEY = r"Software\Hoshimikan6490\Process Priority Manager"

# Registered only when the UpdateCheck feature is enabled.
UPDATE_COMPONENT = f"""<Component Id="cmp_updatecheck" Directory="APPLICATIONFOLDER" Guid="6F1D3C52-8B1E-4D8A-9A57-2C3E5B7A9D10">
      <RegistryValue Root="HKMU" Key="{REG_KEY}" Name="CheckUpdates" Type="integer" Value="1" KeyPath="yes" />
    </Component>
    """

# Hidden feature toggled by the CHECKUPDATES property (checkbox / silent install).
UPDATE_FEATURE = """  <Feature Id="UpdateCheck" Title="更新の定期確認 (GitHub Releases)" Level="1" Display="hidden">
        <Level Value="0" Condition="NOT CHECKUPDATES OR CHECKUPDATES = &quot;0&quot;" />
        <ComponentRef Id="cmp_updatecheck" />
      </Feature>
    """

UI_PROPERTIES = (
    '<Property Id="ApplicationFolderName" Value="Process Priority Manager" />\n'
    '    <Property Id="WixAppFolder" Value="WixPerUserFolder" />\n'
    '    <Property Id="REBOOT" Value="ReallySuppress" />\n'
    '    <WixVariable Id="WixUILicenseRtf" Value="license.rtf" />\n'
    '    <UIRef Id="PPM_UI" />\n    '
)


def run(*cmd):
    print(">", " ".join(map(str, cmd)))
    subprocess.run(cmd, check=True, cwd=ROOT)


def sub1(pattern, repl, text):
    """Replace exactly one match; abort if the generated .wxs layout changed."""
    new, n = re.subn(pattern, repl, text, count=1)
    if n != 1:
        sys.exit(f"transform failed (pattern not found): {pattern}")
    return new


def transform(s):
    # Install scope (per-user / all users) is chosen at install time.
    s = sub1(r'Scope="perUser"', 'Scope="perUserOrMachine"', s)
    s = sub1(r'Language="1033"', 'Language="1041"', s)

    # Install folder: WixUI requires the directory id APPLICATIONFOLDER. The default
    # path is set per scope in UI.wxs; the Directory tree only needs to exist.
    s = sub1(
        r'<StandardDirectory Id="LocalAppDataFolder">\s*'
        r'<Directory Id="dir_programs" Name="Programs">\s*'
        r'(<Directory Id="INSTALLFOLDER" Name="[^"]*">)',
        lambda m: '<StandardDirectory Id="ProgramFiles6432Folder">\n        ' + m.group(1),
        s,
    )
    s = sub1(
        r'</Directory>\s*</Directory>\s*</StandardDirectory>\s*'
        r'<StandardDirectory Id="ProgramMenuFolder">',
        '</Directory>\n    </StandardDirectory>\n    <StandardDirectory Id="ProgramMenuFolder">',
        s,
    )
    s = s.replace("INSTALLFOLDER", "APPLICATIONFOLDER")

    # Registry follows the install scope.
    s = s.replace('Root="HKCU"', 'Root="HKMU"')

    # Update-check component/feature; the main feature is hidden (no feature tree UI).
    s = sub1(r'<Feature Id="Main"', lambda m: UPDATE_COMPONENT + m.group(0), s)
    s = sub1(r'</Feature>(\s*)</Package>', lambda m: UPDATE_FEATURE + "</Feature>" + m.group(1) + "</Package>", s)

    # UI properties, license and UI reference (installer/UI.wxs, installer/license.rtf).
    s = sub1(r'<Feature Id="Main"', lambda m: UI_PROPERTIES + '<Feature Id="Main" Display="hidden"', s)
    return s


def main():
    run("uvx", "pyappdist", "build-image", TARGET)
    run("uvx", "pyappdist", "gen-wix", TARGET)
    # The base .wxs references this product icon but pyappdist doesn't emit it here.
    shutil.copyfile(ROOT / "assets" / "icon.ico", BUILD / "pyappdist_product.ico")
    CUSTOM_WXS.write_text(transform(BASE_WXS.read_text(encoding="utf-8")), encoding="utf-8")

    version = re.search(r'Version="([^"]+)"', CUSTOM_WXS.read_text(encoding="utf-8")).group(1)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    msi = OUT_DIR / f"process-priority-manager-{version}.msi"
    run(
        "wix", "build", str(CUSTOM_WXS), str(INSTALLER / "UI.wxs"),
        "-ext", "WixToolset.UI.wixext", "-culture", "ja-JP",
        "-b", str(BUILD / "image"), "-b", str(BUILD), "-b", str(INSTALLER),
        "-arch", "x64", "-o", str(msi),
    )
    print("OK:", msi)


if __name__ == "__main__":
    main()
