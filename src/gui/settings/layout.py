import tkinter as tk
from src.gui.interfaces import LabelFrame, Frame
from src.common import config, settings


class Layout(LabelFrame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, 'Layout', **kwargs)

        self.record_layout = tk.BooleanVar(value=settings.record_layout)

        row = Frame(self)
        row.pack(side=tk.TOP, fill='x', expand=True, pady=5, padx=5)
        self.check = tk.Checkbutton(
            row,
            variable=self.record_layout,
            text='Record layout',
            command=self._on_change
        )
        self.check.pack(side=tk.LEFT)

    def _on_change(self):
        if self.record_layout.get() and config.layout is None:
            print('\n[!] Load a routine before recording a layout')
            self.record_layout.set(False)
            settings.record_layout = False
            return

        settings.record_layout = self.record_layout.get()
        state = 'enabled' if settings.record_layout else 'disabled'
        print(f'\n[~] Layout recording {state}')
