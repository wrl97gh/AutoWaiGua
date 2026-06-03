"""Creates a desktop launcher that can run Auto Maple from anywhere."""

import argparse
import os
import stat
import sys

from src.common import platform


def create_windows_shortcut():
    import ctypes
    import win32com.client as client

    cwd = os.getcwd()
    target = os.path.join(os.environ['WINDIR'], 'System32', 'cmd.exe')
    flag = '/k' if args.stay else '/c'

    shell = client.Dispatch('WScript.Shell')
    shortcut_path = os.path.join(shell.SpecialFolders('Desktop'), 'Auto Maple.lnk')
    shortcut = shell.CreateShortCut(shortcut_path)
    shortcut.Targetpath = target
    shortcut.Arguments = flag + f' "cd {cwd} & python main.py"'
    shortcut.IconLocation = os.path.join(cwd, 'assets', 'icon.ico')
    try:
        shortcut.save()
    except Exception:
        ctypes.windll.shell32.ShellExecuteW(
            None,
            'runas',
            sys.executable,
            ' '.join(sys.argv),
            None,
            1,
        )
        return

    with open(shortcut_path, 'rb') as lnk:
        arr = bytearray(lnk.read())
    arr[0x15] = arr[0x15] | 0x20
    with open(shortcut_path, 'wb') as lnk:
        lnk.write(arr)

    print(f" ~  Created Windows shortcut: {shortcut_path}")


def create_macos_launcher():
    cwd = os.getcwd()
    launcher_path = os.path.join(platform.desktop_dir(), 'Auto Maple.command')
    python = sys.executable
    stay = 'read -n 1 -s -r -p "Press any key to close..."' if args.stay else ''
    script = f"""#!/bin/zsh
cd "{cwd}"
"{python}" main.py
{stay}
"""
    with open(launcher_path, 'w', encoding='utf-8') as file:
        file.write(script)
    mode = os.stat(launcher_path).st_mode
    os.chmod(launcher_path, mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    print(f" ~  Created macOS launcher: {launcher_path}")


def create_desktop_launcher():
    print('\n[~] Creating desktop launcher for Auto Maple:')
    if platform.IS_WINDOWS:
        create_windows_shortcut()
    elif platform.IS_MACOS:
        create_macos_launcher()
    else:
        print(' !  Desktop launcher setup is currently supported on Windows and macOS only.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--stay', action='store_true')
    args = parser.parse_args()

    create_desktop_launcher()
