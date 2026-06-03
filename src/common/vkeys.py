"""Compatibility wrapper for keyboard and mouse controls.

Older command books import from src.common.vkeys directly. Keep that public API
while routing the implementation through the cross-platform controls module.
"""

from src.common.controls import click, key_down, key_up, press

__all__ = ['click', 'key_down', 'key_up', 'press']
