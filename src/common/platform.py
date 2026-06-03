"""Small cross-platform helpers for OS features used by Auto Maple."""

import os
import platform as _platform
import subprocess
import time


SYSTEM = _platform.system().lower()
IS_WINDOWS = SYSTEM == 'windows'
IS_MACOS = SYSTEM == 'darwin'


def find_window_rect(title='MapleStory', default=None):
    """Return a window rect as (left, top, right, bottom), or DEFAULT if not found."""

    if default is None:
        default = (0, 0, 1366, 768)

    if IS_WINDOWS:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        handle = user32.FindWindowW(None, title)
        if not handle:
            return default
        rect = wintypes.RECT()
        user32.GetWindowRect(handle, ctypes.pointer(rect))
        return rect.left, rect.top, rect.right, rect.bottom

    if IS_MACOS:
        try:
            import Quartz
        except ImportError:
            return default

        options = Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements
        windows = Quartz.CGWindowListCopyWindowInfo(options, Quartz.kCGNullWindowID) or []
        title_lower = title.lower()
        for window in windows:
            name = (window.get('kCGWindowName') or '').lower()
            owner = (window.get('kCGWindowOwnerName') or '').lower()
            if title_lower in name or title_lower in owner:
                bounds = window.get('kCGWindowBounds') or {}
                left = int(bounds.get('X', 0))
                top = int(bounds.get('Y', 0))
                width = int(bounds.get('Width', default[2] - default[0]))
                height = int(bounds.get('Height', default[3] - default[1]))
                return left, top, left + width, top + height

    return default


def set_process_dpi_aware():
    """Enable DPI awareness where the host OS supports it."""

    if not IS_WINDOWS:
        return
    try:
        import ctypes
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def beep(frequency=523, duration=200):
    """Play a short notification beep."""

    if IS_WINDOWS:
        try:
            import winsound
            winsound.Beep(frequency, duration)
            return
        except Exception:
            pass

    if IS_MACOS:
        try:
            subprocess.run(
                ['osascript', '-e', 'beep 1'],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass
    else:
        print('\a', end='', flush=True)
    time.sleep(duration / 1000)


def desktop_dir():
    return os.path.join(os.path.expanduser('~'), 'Desktop')
