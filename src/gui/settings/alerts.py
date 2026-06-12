import tkinter as tk
from src.common import config
from src.common.interfaces import Configurable
from src.gui.interfaces import LabelFrame, Frame


class Alerts(LabelFrame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, 'Alerts', **kwargs)

        self.alert_settings = AlertSettings('alerts')
        self.ignore_siren = tk.BooleanVar(
            value=self.alert_settings.get('Ignore siren alerts')
        )
        config.ignore_siren_alerts = self.ignore_siren.get()

        row = Frame(self)
        row.pack(side=tk.TOP, fill='x', expand=True, pady=5, padx=5)
        tk.Checkbutton(
            row,
            variable=self.ignore_siren,
            text='Ignore siren alerts',
            command=self._on_change
        ).pack(side=tk.LEFT)

    def _on_change(self):
        value = self.ignore_siren.get()
        config.ignore_siren_alerts = value
        self.alert_settings.set('Ignore siren alerts', value)
        self.alert_settings.save_config()


class AlertSettings(Configurable):
    DEFAULT_CONFIG = {
        'Ignore siren alerts': False
    }

    def get(self, key):
        return self.config[key]

    def set(self, key, value):
        assert key in self.config
        self.config[key] = value
