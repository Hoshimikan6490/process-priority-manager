"""Build the MSI: pyappdist builds the app image + base .wxs, then this script
customises the .wxs (install scope, install folder, update-check option)."""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = "windowsmsi"
BUILD = ROOT / ".appdist-build" / TARGET
WXS = BUILD / "process-priority-manager.wxs"
OUT_DIR = ROOT / "appdist" / TARGET / "dist"


def run(*cmd):
    print(">", " ".join(map(str, cmd)))
    subprocess.run(cmd, check=True, cwd=ROOT)


def sub1(pattern, repl, text, flags=0):
    new, n = re.subn(pattern, repl, text, count=1, flags=flags)
    if n != 1:
        sys.exit(f"transform failed (pattern not found): {pattern}")
    return new


def transform(s):
    # 1. 現在のユーザー / 全ユーザーを実行時に選択可能にする
    s = sub1(r'Scope="perUser"', 'Scope="perUserOrMachine"', s)
    s = sub1(r'Language="1033"', 'Language="1041"', s)

    # 2. インストール先: WixUI_Advanced 用の配置 (per-machine は Program Files、
    #    per-user は %LOCALAPPDATA%\Apps。いずれもインストール先ダイアログで変更可)
    s = sub1(
        r'<StandardDirectory Id="LocalAppDataFolder">\s*'
        r'<Directory Id="dir_programs" Name="Programs">\s*'
        r'(<Directory Id="INSTALLFOLDER" Name="[^"]*">)',
        r'<StandardDirectory Id="ProgramFiles6432Folder">\n        \1',
        s,
    )
    s = sub1(
        r'</Directory>\s*</Directory>\s*</StandardDirectory>\s*'
        r'<StandardDirectory Id="ProgramMenuFolder">',
        '</Directory>\n    </StandardDirectory>\n'
        '    <StandardDirectory Id="ProgramMenuFolder">',
        s,
    )

    # 3. レジストリはスコープに追従 (HKMU) + 更新確認設定を書き込む
    s = s.replace('Root="HKCU"', 'Root="HKMU"')
    reg = (
        r'<RegistryValue Root="HKMU" Key="Software\Hoshimikan6490\Process Priority Manager" '
        r'Name="CheckUpdates" Type="string" Value="[CHECKUPDATES]" />'
    )
    s = sub1(
        r'(<Component Id="cmp_registry"[^>]*>)',
        lambda m: m.group(1) + "\n            " + reg,
        s,
    )

    # WixUI_Advanced はインストール先ディレクトリ ID に APPLICATIONFOLDER を要求する
    s = s.replace('INSTALLFOLDER', 'APPLICATIONFOLDER')

    # 4. UI
    s = sub1(
        r'(<Feature Id="Main")',
        '<Property Id="ApplicationFolderName" Value="Process Priority Manager" />\n'
        '    <Property Id="WixAppFolder" Value="WixPerUserFolder" />\n'
        '    <ui:WixUI Id="WixUI_Advanced" />\n    \\1',
        s,
    )
    s = sub1(r'<Wix xmlns="([^"]+)">', r'<Wix xmlns="\1" xmlns:ui="http://wixtoolset.org/schemas/v4/wxs/ui">', s)
    return s


def main():
    run("uvx", "pyappdist", "build-image", TARGET)
    run("uvx", "pyappdist", "gen-wix", TARGET)
    out = BUILD / "ppm.wxs"
    out.write_text(transform(WXS.read_text(encoding="utf-8")), encoding="utf-8")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    version = re.search(r'Version="([^"]+)"', out.read_text(encoding="utf-8")).group(1)
    msi = OUT_DIR / f"process-priority-manager-{version}.msi"
    run(
        "wix", "build", str(out), str(ROOT / "installer" / "UI.wxs"),
        "-ext", "WixToolset.UI.wixext", "-culture", "ja-JP",
        "-b", str(BUILD / "image"), "-b", str(BUILD),
        "-arch", "x64", "-o", str(msi),
    )
    print("OK:", msi)


if __name__ == "__main__":
    main()
