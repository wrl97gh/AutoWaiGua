import tkinter as tk
from src.gui.interfaces import LabelFrame, Frame
from src.common.interfaces import Configurable


class Runes(LabelFrame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, 'Runes', **kwargs)

        self.rune_settings = RuneSettings('runes')
        self.save_debug = tk.BooleanVar(value=self.rune_settings.get('Save debug screenshots'))
        self.save_dataset = tk.BooleanVar(value=self.rune_settings.get('Save rune screenshots'))
        self.confirm_twice = tk.BooleanVar(value=self.rune_settings.get('Confirm solution twice'))
        self.detection_engine = tk.StringVar(value=self.rune_settings.get('Detection engine'))

        debug_row = Frame(self)
        debug_row.pack(side=tk.TOP, fill='x', expand=True, pady=5, padx=5)
        debug_check = tk.Checkbutton(
            debug_row,
            variable=self.save_debug,
            text='Save debug screenshots',
            command=self._on_change
        )
        debug_check.pack(side=tk.LEFT)

        dataset_row = Frame(self)
        dataset_row.pack(side=tk.TOP, fill='x', expand=True, pady=(0, 5), padx=5)
        dataset_check = tk.Checkbutton(
            dataset_row,
            variable=self.save_dataset,
            text='Save rune screenshots (for labeling)',
            command=self._on_change
        )
        dataset_check.pack(side=tk.LEFT)

        confirm_row = Frame(self)
        confirm_row.pack(side=tk.TOP, fill='x', expand=True, pady=(0, 5), padx=5)
        confirm_check = tk.Checkbutton(
            confirm_row,
            variable=self.confirm_twice,
            text='Confirm solution twice',
            command=self._on_change
        )
        confirm_check.pack(side=tk.LEFT)

        engine_row = Frame(self)
        engine_row.pack(side=tk.TOP, fill='x', expand=True, pady=(0, 5), padx=5)
        tk.Label(engine_row, text='Detection engine').pack(side=tk.LEFT, padx=(0, 8))
        tk.Radiobutton(
            engine_row,
            variable=self.detection_engine,
            value='detection1',
            text='Detection 1',
            command=self._on_change
        ).pack(side=tk.LEFT)
        tk.Radiobutton(
            engine_row,
            variable=self.detection_engine,
            value='detection2',
            text='Detection 2',
            command=self._on_change
        ).pack(side=tk.LEFT)

    def _on_change(self):
        self.rune_settings.set('Save debug screenshots', self.save_debug.get())
        self.rune_settings.set('Save rune screenshots', self.save_dataset.get())
        self.rune_settings.set('Confirm solution twice', self.confirm_twice.get())
        self.rune_settings.set('Detection engine', self.detection_engine.get())
        self.rune_settings.save_config()


class RuneSettings(Configurable):
    DEFAULT_CONFIG = {
        'Save debug screenshots': False,
        'Save rune screenshots': True,
        'Confirm solution twice': True,
        'Detection engine': 'detection1'
    }

    def get(self, key):
        value = self.config.get(key, '')
        if value == '':
            value = self.DEFAULT_CONFIG[key]
            self.config[key] = value
            self.save_config()
        return value

    def set(self, key, value):
        assert key in self.config
        self.config[key] = value
