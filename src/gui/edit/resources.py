"""Command book, routine, and save controls for the Edit tab."""

import os
import tkinter as tk
from tkinter import ttk
from tkinter.filedialog import askopenfilename, asksaveasfilename
from tkinter.messagebox import askyesno

from src.common import config
from src.gui.interfaces import LabelFrame


class Resources(LabelFrame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, 'Resources', **kwargs)

        self.command_book_var = tk.StringVar()
        self.routine_var = tk.StringVar()
        self.command_books = {}
        self.routines = {}

        self.columnconfigure(1, weight=1)
        self.columnconfigure(4, weight=2)

        tk.Label(self, text='Command Book').grid(
            row=0, column=0, padx=(8, 5), pady=7, sticky=tk.W
        )
        self.command_book = ttk.Combobox(
            self,
            textvariable=self.command_book_var,
            state='readonly',
            width=22
        )
        self.command_book.grid(row=0, column=1, sticky=tk.EW, pady=7)
        self.command_book.bind('<<ComboboxSelected>>', lambda _: self.load_command_book())
        tk.Button(self, text='Browse...', command=self.browse_command_book).grid(
            row=0, column=2, padx=(5, 14), pady=7
        )

        tk.Label(self, text='Routine').grid(
            row=0, column=3, padx=(0, 5), pady=7, sticky=tk.W
        )
        self.routine = ttk.Combobox(
            self,
            textvariable=self.routine_var,
            state=tk.DISABLED,
            width=28
        )
        self.routine.grid(row=0, column=4, sticky=tk.EW, pady=7)
        self.routine.bind('<<ComboboxSelected>>', lambda _: self.load_routine())
        self.routine_browse = tk.Button(
            self,
            text='Browse...',
            command=self.browse_routine,
            state=tk.DISABLED
        )
        self.routine_browse.grid(row=0, column=5, padx=(5, 8), pady=7)
        self.save_button = tk.Button(
            self,
            text='Save Routine',
            command=self.save_routine,
            state=tk.DISABLED
        )
        self.save_button.grid(row=0, column=6, padx=(4, 8), pady=7)

        self.refresh_command_books()

    def refresh_command_books(self):
        directory = os.path.join(config.RESOURCES_DIR, 'command_books')
        paths = sorted(
            os.path.join(directory, name)
            for name in os.listdir(directory)
            if name.endswith('.py') and not name.startswith('_')
        ) if os.path.isdir(directory) else []
        self.command_books = {
            os.path.splitext(os.path.basename(path))[0]: path for path in paths
        }
        self.command_book.configure(values=list(self.command_books))
        self.sync_selection()

    def refresh_routines(self):
        self.routines = {}
        command_book = config.bot.command_book
        if command_book is not None:
            directory = os.path.join(
                config.RESOURCES_DIR, 'routines', command_book.name
            )
            if os.path.isdir(directory):
                paths = sorted(
                    os.path.join(directory, name)
                    for name in os.listdir(directory)
                    if name.endswith('.csv')
                )
                self.routines = {
                    os.path.basename(path): path for path in paths
                }

        enabled = bool(self.routines) or config.bot.command_book is not None
        self.routine.configure(
            values=list(self.routines),
            state='readonly' if enabled else tk.DISABLED
        )
        self.routine_browse.configure(
            state=tk.NORMAL if enabled else tk.DISABLED
        )

    def sync_selection(self):
        command_book = config.bot.command_book
        if command_book is None:
            self.command_book_var.set('')
            self.routine_var.set('')
        else:
            self.command_book_var.set(command_book.name)
            self.refresh_routines()
            if config.routine.path:
                self.routine_var.set(os.path.basename(config.routine.path))
            else:
                self.routine_var.set('')

        self.update_save_state()

        gui = config.gui
        if hasattr(gui, 'layout_builder'):
            gui.layout_builder.sync_target()

    def update_save_state(self):
        command_book = config.bot.command_book
        self.save_button.configure(
            state=tk.NORMAL
            if command_book is not None and len(config.routine) > 0
            else tk.DISABLED
        )

    def load_command_book(self, path=None):
        if config.enabled:
            print('\n[!] Cannot load command books while Auto Maple is enabled')
            self.sync_selection()
            return
        if not self._confirm_discard(
                'Load Command Book',
                'Loading a new command book will discard the current routine.'
        ):
            self.sync_selection()
            return

        path = path or self.command_books.get(self.command_book_var.get())
        if path and config.bot.load_commands(path):
            self.refresh_command_books()
            self.refresh_routines()
            self.routine_var.set('')
        else:
            self.sync_selection()

    def load_routine(self, path=None):
        if config.enabled:
            print('\n[!] Cannot load routines while Auto Maple is enabled')
            self.sync_selection()
            return
        if config.bot.command_book is None:
            print('\n[!] Select a command book before loading a routine')
            return
        if not self._confirm_discard(
                'Load Routine',
                'The current routine has unsaved changes.'
        ):
            self.sync_selection()
            return

        path = path or self.routines.get(self.routine_var.get())
        if path:
            config.routine.load(path)
        self.sync_selection()

    def browse_command_book(self):
        path = askopenfilename(
            initialdir=os.path.join(config.RESOURCES_DIR, 'command_books'),
            title='Select a command book',
            filetypes=[('Python command book', '*.py')]
        )
        if path:
            self.load_command_book(path)

    def browse_routine(self):
        command_book = config.bot.command_book
        if command_book is None:
            return
        directory = os.path.join(
            config.RESOURCES_DIR, 'routines', command_book.name
        )
        os.makedirs(directory, exist_ok=True)
        path = askopenfilename(
            initialdir=directory,
            title='Select a routine',
            filetypes=[('Routine CSV', '*.csv')]
        )
        if path:
            self.load_routine(path)

    def save_routine(self):
        if config.enabled:
            print('\n[!] Cannot save routines while Auto Maple is enabled')
            return
        if config.bot.command_book is None or len(config.routine) == 0:
            print('\n[!] Load or create a routine before saving')
            return

        path = config.routine.path
        if not path:
            directory = os.path.join(
                config.RESOURCES_DIR,
                'routines',
                config.bot.command_book.name
            )
            os.makedirs(directory, exist_ok=True)
            path = asksaveasfilename(
                initialdir=directory,
                title='Save routine',
                filetypes=[('Routine CSV', '*.csv')],
                defaultextension='.csv'
            )
        if path:
            config.routine.save(path)
            self.refresh_routines()
            self.sync_selection()

    @staticmethod
    def _confirm_discard(title, message):
        if not config.routine.dirty:
            return True
        return askyesno(
            title=title,
            message=f'{message} Would you like to proceed anyway?',
            icon='warning'
        )
