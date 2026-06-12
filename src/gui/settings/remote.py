import tkinter as tk
from src.common import config
from src.gui.interfaces import LabelFrame, Frame


class RemoteControl(LabelFrame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, 'Remote Control (Telegram)', **kwargs)

        self.token = tk.StringVar()
        self.chat_id = tk.StringVar()
        if config.remote is not None:
            self.token.set(config.remote.config['Telegram bot token'])
            self.chat_id.set(config.remote.config['Telegram chat id'])

        token_row = Frame(self)
        token_row.pack(side=tk.TOP, fill='x', expand=True, pady=(5, 0), padx=5)
        tk.Label(token_row, text='Bot token', width=8, anchor='w').pack(side=tk.LEFT)
        tk.Entry(token_row, textvariable=self.token, show='*').pack(side=tk.LEFT, fill='x', expand=True)

        chat_row = Frame(self)
        chat_row.pack(side=tk.TOP, fill='x', expand=True, pady=(5, 0), padx=5)
        tk.Label(chat_row, text='Chat id', width=8, anchor='w').pack(side=tk.LEFT)
        tk.Entry(chat_row, textvariable=self.chat_id).pack(side=tk.LEFT, fill='x', expand=True)

        button_row = Frame(self)
        button_row.pack(side=tk.TOP, fill='x', expand=True, pady=5, padx=5)
        tk.Button(button_row, text='Save', command=self._save).pack(side=tk.LEFT)
        tk.Button(button_row, text='Send test message', command=self._test).pack(side=tk.LEFT, padx=(10, 0))

    def _save(self):
        if config.remote is None:
            return
        config.remote.config['Telegram bot token'] = self.token.get().strip()
        config.remote.config['Telegram chat id'] = self.chat_id.get().strip()
        config.remote.save_config()
        print('\n[~] Saved remote control settings')

    def _test(self):
        self._save()
        if config.remote is None:
            return
        if not config.remote.config['Telegram bot token']:
            print('\n[!] Set a Telegram bot token first')
        elif not config.remote.config['Telegram chat id']:
            print('\n[!] No chat id set. Send any message to your bot, '
                  'then copy the id printed in this console.')
        else:
            config.remote.notify('Test message from Auto Maple')
            print('\n[~] Test message queued')
