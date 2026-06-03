"""Keyboard and mouse primitives with Windows and macOS implementations."""

import time
from random import random

from pynput import keyboard, mouse

from src.common import config, platform


_keyboard = keyboard.Controller()
_mouse = mouse.Controller()
_pressed = set()
_warned_invalid_keys = set()
_quartz = None
if platform.IS_MACOS:
    try:
        import Quartz as _quartz
    except ImportError:
        _quartz = None


def _key(name):
    return getattr(keyboard.Key, name, None)


SPECIAL_KEYS = {
    'left': _key('left'),
    'up': _key('up'),
    'right': _key('right'),
    'down': _key('down'),
    'backspace': _key('backspace'),
    'tab': _key('tab'),
    'enter': _key('enter'),
    'shift': _key('shift'),
    'ctrl': _key('ctrl'),
    'alt': _key('alt'),
    'cmd': _key('cmd'),
    'caps lock': _key('caps_lock'),
    'esc': _key('esc'),
    'space': _key('space'),
    'page up': _key('page_up'),
    'page down': _key('page_down'),
    'end': _key('end'),
    'home': _key('home'),
    'insert': _key('insert'),
    'delete': _key('delete'),
    'f1': _key('f1'),
    'f2': _key('f2'),
    'f3': _key('f3'),
    'f4': _key('f4'),
    'f5': _key('f5'),
    'f6': _key('f6'),
    'f7': _key('f7'),
    'f8': _key('f8'),
    'f9': _key('f9'),
    'f10': _key('f10'),
    'f11': _key('f11'),
    'f12': _key('f12'),
}
SPECIAL_KEYS = {name: key for name, key in SPECIAL_KEYS.items() if key is not None}

KEY_ALIASES = {
    'escape': 'esc',
    'return': 'enter',
    'control': 'ctrl',
    'option': 'alt',
    'command': 'cmd',
    'capslock': 'caps lock',
    'caps_lock': 'caps lock',
    'pageup': 'page up',
    'pagedown': 'page down',
    'comma': ',',
    'period': '.',
    'dot': '.',
    'slash': '/',
    'forward slash': '/',
    'backslash': '\\',
    'semicolon': ';',
    'semi-colon': ';',
    'quote': "'",
    'apostrophe': "'",
    'minus': '-',
    'hyphen': '-',
    'dash': '-',
    'equals': '=',
    'equal': '=',
    'left bracket': '[',
    'right bracket': ']',
    'open bracket': '[',
    'close bracket': ']',
    'grave': '`',
    'backtick': '`',
}

MACOS_KEYCODES = {
    'a': 0, 's': 1, 'd': 2, 'f': 3, 'h': 4, 'g': 5, 'z': 6, 'x': 7,
    'c': 8, 'v': 9, 'b': 11, 'q': 12, 'w': 13, 'e': 14, 'r': 15,
    'y': 16, 't': 17, '1': 18, '2': 19, '3': 20, '4': 21, '6': 22,
    '5': 23, '=': 24, '9': 25, '7': 26, '-': 27, '8': 28, '0': 29,
    ']': 30, 'o': 31, 'u': 32, '[': 33, 'i': 34, 'p': 35, 'enter': 36,
    'l': 37, 'j': 38, "'": 39, 'k': 40, ';': 41, '\\': 42, ',': 43,
    '/': 44, 'n': 45, 'm': 46, '.': 47, 'tab': 48, 'space': 49,
    '`': 50, 'backspace': 51, 'esc': 53, 'cmd': 55, 'shift': 56,
    'caps lock': 57, 'alt': 58, 'ctrl': 59, 'f5': 96, 'f6': 97,
    'f7': 98, 'f3': 99, 'f8': 100, 'f9': 101, 'f11': 103, 'f13': 105,
    'f16': 106, 'f14': 107, 'f10': 109, 'f12': 111, 'f15': 113,
    'home': 115, 'page up': 116, 'delete': 117, 'f4': 118, 'end': 119,
    'f2': 120, 'page down': 121, 'f1': 122, 'left': 123, 'right': 124,
    'down': 125, 'up': 126,
}
MACOS_QUARTZ_KEYS = set('0123456789')

MOUSE_BUTTONS = {
    'left': mouse.Button.left,
    'right': mouse.Button.right,
}


def canonical_key_name(key):
    """Return the keybinding name used by Auto Maple."""

    if isinstance(key, str):
        return key.lower()

    char = getattr(key, 'char', None)
    if char:
        return char.lower()

    for name, special in SPECIAL_KEYS.items():
        if key == special:
            return name

    text = str(key)
    if text.startswith('Key.'):
        return text[4:].replace('_', ' ')
    return text.lower()


def tk_event_to_key_name(event):
    """Convert a Tk key event into the same names used by pynput."""

    name = (event.keysym or '').lower()
    aliases = {
        'escape': 'esc',
        'return': 'enter',
        'prior': 'page up',
        'next': 'page down',
        'control_l': 'ctrl',
        'control_r': 'ctrl',
        'shift_l': 'shift',
        'shift_r': 'shift',
        'alt_l': 'alt',
        'alt_r': 'alt',
        'option_l': 'alt',
        'option_r': 'alt',
        'command': 'cmd',
        'command_l': 'cmd',
        'command_r': 'cmd',
        'caps_lock': 'caps lock',
        'comma': ',',
        'period': '.',
        'slash': '/',
        'backslash': '\\',
        'semicolon': ';',
        'apostrophe': "'",
        'quoteright': "'",
        'minus': '-',
        'equal': '=',
        'bracketleft': '[',
        'bracketright': ']',
        'quoteleft': '`',
        'grave': '`',
    }
    if len(name) == 1:
        return name
    return aliases.get(name, name.replace('_', ' '))


def _to_pynput_key(key):
    if key is None or key == '':
        return None

    key = KEY_ALIASES.get(str(key).strip().lower(), str(key).strip().lower())
    if key in SPECIAL_KEYS:
        return SPECIAL_KEYS[key]
    if len(key) == 1:
        return key
    if key not in _warned_invalid_keys:
        print(f"Invalid keyboard input: '{key}'.")
        _warned_invalid_keys.add(key)
    return None


def _normalize_key(key):
    if key is None:
        return None
    return KEY_ALIASES.get(str(key).strip().lower(), str(key).strip().lower())


def _send_macos_key(key, is_down):
    if _quartz is None:
        return False

    key = _normalize_key(key)
    keycode = MACOS_KEYCODES.get(key)
    if keycode is None:
        return False

    event = _quartz.CGEventCreateKeyboardEvent(None, keycode, is_down)
    _quartz.CGEventPost(_quartz.kCGHIDEventTap, event)
    return True


def _on_press(key):
    _pressed.add(canonical_key_name(key))


def _on_release(key):
    _pressed.discard(canonical_key_name(key))


_listener = keyboard.Listener(on_press=_on_press, on_release=_on_release)
_listener.daemon = True
_listener.start()


def is_pressed(key):
    if key is None:
        return False
    key = _normalize_key(key)
    return key in _pressed


def run_if_enabled(function):
    def wrapper(*args, **kwargs):
        if config.enabled:
            return function(*args, **kwargs)
    return wrapper


@run_if_enabled
def key_down(key):
    normalized = _normalize_key(key)
    if platform.IS_MACOS and normalized in MACOS_QUARTZ_KEYS and _send_macos_key(normalized, True):
        return

    key = _to_pynput_key(normalized)
    if key is not None:
        _keyboard.press(key)


def key_up(key):
    normalized = _normalize_key(key)
    if platform.IS_MACOS and normalized in MACOS_QUARTZ_KEYS and _send_macos_key(normalized, False):
        return

    key = _to_pynput_key(normalized)
    if key is not None:
        _keyboard.release(key)


@run_if_enabled
def press(key, n, down_time=0.05, up_time=0.1):
    if key is None or key == '':
        return

    for _ in range(n):
        key_down(key)
        time.sleep(down_time * (0.8 + 0.4 * random()))
        key_up(key)
        time.sleep(up_time * (0.8 + 0.4 * random()))


@run_if_enabled
def click(position, button='left'):
    if button not in MOUSE_BUTTONS:
        print(f"'{button}' is not a valid mouse button.")
        return
    _mouse.position = position
    _mouse.click(MOUSE_BUTTONS[button])
