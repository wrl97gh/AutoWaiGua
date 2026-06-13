"""Displays Auto Maple's current settings and allows the user to edit them."""

import tkinter as tk
from src.gui.interfaces import KeyBindings
from src.gui.settings.pets import Pets
from src.gui.settings.runes import Runes
from src.gui.settings.alerts import Alerts
from src.gui.settings.remote import RemoteControl
from src.gui.interfaces import Tab, Frame
from src.common import config


class Settings(Tab):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, 'Settings', **kwargs)

        self.columnconfigure(0, weight=1, uniform='settings')
        self.columnconfigure(1, weight=1, uniform='settings')
        self.rowconfigure(0, weight=1)

        self.column1 = Frame(self)
        self.column1.grid(
            row=0, column=0, sticky=tk.NSEW, padx=(10, 5), pady=10
        )
        self.controls = KeyBindings(self.column1, 'Auto Maple Controls', config.listener, scroll_height=95)
        self.controls.pack(side=tk.TOP, fill='x', expand=True)
        self.common_bindings = KeyBindings(self.column1, 'In-game Keybindings', config.bot, scroll_height=80)
        self.common_bindings.pack(side=tk.TOP, fill='x', expand=True, pady=(10, 0))
        self.pets = Pets(self.column1)
        self.pets.pack(side=tk.TOP, fill='x', expand=True, pady=(10, 0))
        self.runes = Runes(self.column1)
        self.runes.pack(side=tk.TOP, fill='x', expand=True, pady=(10, 0))
        self.alerts = Alerts(self.column1)
        self.alerts.pack(side=tk.TOP, fill='x', expand=True, pady=(10, 0))

        self.column2 = Frame(self)
        self.column2.grid(
            row=0, column=1, sticky=tk.NSEW, padx=(5, 10), pady=10
        )
        self.remote = RemoteControl(self.column2)
        self.remote.pack(side=tk.TOP, fill='x', expand=True)
        self.class_bindings = KeyBindings(self.column2, f'No Command Book Selected', None)
        self.class_bindings.pack(side=tk.TOP, fill='x', expand=True, pady=(10, 0))

    def update_class_bindings(self):
        self.class_bindings.destroy()
        class_name = config.bot.command_book.name.capitalize()
        self.class_bindings = KeyBindings(
            self.column2,
            f'{class_name} Keybindings',
            config.bot.command_book,
            scroll_height=520
        )
        self.class_bindings.pack(side=tk.TOP, fill='x', expand=True, pady=(10, 0))
