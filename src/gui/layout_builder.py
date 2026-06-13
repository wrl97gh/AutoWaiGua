"""GUI page for building Layout files from the minimap."""

import os
import queue
import threading
import tkinter as tk
from tkinter.filedialog import askopenfilenames
from tkinter.messagebox import showerror

from PIL import Image, ImageTk

from src.common import config
from src.gui.interfaces import Frame, LabelFrame, Tab
from src.routine import layout_builder


class LayoutBuilder(Tab):
    PREVIEW_SIZE = (720, 430)

    def __init__(self, parent, **kwargs):
        super().__init__(parent, 'Layout', **kwargs)

        self.command_book_var = tk.StringVar(value='Not selected')
        self.routine_var = tk.StringVar(value='Not selected')
        self.mode = tk.StringVar(value='live')
        self.duration = tk.IntVar(value=90)
        self.files_var = tk.StringVar(value='No screenshots selected')
        self.preview_only = tk.BooleanVar(value=False)
        self.status = tk.StringVar(
            value='Load a Command Book and Routine, then choose a source.'
        )
        self.files = []
        self.task = None
        self.task_options = None
        self.stop_event = threading.Event()
        self.events = queue.Queue()
        self.preview_image = None

        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)

        target = LabelFrame(self, 'Layout Target')
        target.grid(row=0, column=0, sticky=tk.EW, padx=12, pady=(12, 6))
        target.columnconfigure(1, weight=1)
        target.columnconfigure(3, weight=1)
        tk.Label(target, text='Command Book').grid(
            row=0, column=0, padx=(8, 5), pady=7
        )
        tk.Entry(
            target, textvariable=self.command_book_var, state=tk.DISABLED
        ).grid(row=0, column=1, sticky=tk.EW, pady=7)
        tk.Label(target, text='Routine').grid(
            row=0, column=2, padx=(14, 5), pady=7
        )
        tk.Entry(
            target, textvariable=self.routine_var, state=tk.DISABLED
        ).grid(row=0, column=3, sticky=tk.EW, padx=(0, 8), pady=7)

        source = LabelFrame(self, 'Source')
        source.grid(row=1, column=0, sticky=tk.EW, padx=12, pady=6)
        source.columnconfigure(4, weight=1)
        tk.Radiobutton(
            source,
            text='Live minimap',
            variable=self.mode,
            value='live',
            command=self._update_source_state
        ).grid(row=0, column=0, padx=(8, 5), pady=7)
        tk.Label(source, text='Duration').grid(row=0, column=1, padx=(8, 4))
        self.duration_input = tk.Spinbox(
            source, from_=15, to=600, textvariable=self.duration, width=5
        )
        self.duration_input.grid(row=0, column=2)
        tk.Label(source, text='seconds').grid(row=0, column=3, padx=(3, 14))
        tk.Radiobutton(
            source,
            text='Saved screenshots',
            variable=self.mode,
            value='screenshots',
            command=self._update_source_state
        ).grid(row=1, column=0, padx=(8, 5), pady=(0, 7))
        self.files_label = tk.Label(
            source, textvariable=self.files_var, anchor=tk.W
        )
        self.files_label.grid(
            row=1, column=1, columnspan=4, sticky=tk.EW, padx=(8, 5), pady=(0, 7)
        )
        self.files_button = tk.Button(
            source, text='Choose...', command=self.choose_files
        )
        self.files_button.grid(row=1, column=5, padx=(0, 8), pady=(0, 7))

        actions = Frame(self)
        actions.grid(row=2, column=0, sticky=tk.EW, padx=12, pady=6)
        tk.Checkbutton(
            actions,
            text='Preview only (do not save)',
            variable=self.preview_only
        ).pack(side=tk.LEFT)
        self.build_button = tk.Button(
            actions, text='Build Layout', command=self.start
        )
        self.build_button.pack(side=tk.RIGHT)
        self.cancel_button = tk.Button(
            actions, text='Cancel', command=self.cancel, state=tk.DISABLED
        )
        self.cancel_button.pack(side=tk.RIGHT, padx=(0, 8))

        preview = LabelFrame(self, 'Preview')
        preview.grid(
            row=3, column=0, sticky=tk.NSEW, padx=12, pady=(6, 6)
        )
        preview.rowconfigure(0, weight=1)
        preview.columnconfigure(0, weight=1)
        self.preview = tk.Label(
            preview,
            text='Red lines are detected platforms; blue dots are path nodes.',
            anchor=tk.CENTER
        )
        self.preview.grid(row=0, column=0, sticky=tk.NSEW, padx=8, pady=8)

        tk.Label(
            self, textvariable=self.status, anchor=tk.W
        ).grid(row=4, column=0, sticky=tk.EW, padx=14, pady=(0, 12))

        self._update_source_state()
        self.sync_target()
        self.after(100, self._process_events)

    def sync_target(self):
        command_book = config.bot.command_book
        self.command_book_var.set(
            command_book.name if command_book is not None else 'Not selected'
        )
        self.routine_var.set(
            os.path.basename(config.routine.path)
            if config.routine.path else 'Not selected'
        )

    def choose_files(self):
        paths = askopenfilenames(
            title='Select full-frame screenshots from one map',
            filetypes=[
                ('Screenshots', '*.png *.jpg *.jpeg'),
                ('All files', '*.*')
            ]
        )
        if paths:
            self.files = list(paths)
            self.files_var.set(f'{len(self.files)} screenshots selected')

    def start(self):
        if self.task is not None and self.task.is_alive():
            return
        if config.bot.command_book is None or not config.routine.path:
            showerror(
                'Layout Builder',
                'Select a Command Book and Routine on the View page first.'
            )
            return
        if self.mode.get() == 'screenshots' and not self.files:
            showerror('Layout Builder', 'Choose at least one screenshot.')
            return

        self.stop_event.clear()
        self.task_options = {
            'mode': self.mode.get(),
            'duration': max(15, int(self.duration.get())),
            'files': list(self.files),
            'dry_run': self.preview_only.get(),
            'routine_path': config.routine.path,
            'routine_name': os.path.splitext(
                os.path.basename(config.routine.path)
            )[0],
            'class_name': config.bot.command_book.name
        }
        self.build_button.configure(state=tk.DISABLED)
        self.cancel_button.configure(state=tk.NORMAL)
        self.status.set('Starting layout build...')
        self.task = threading.Thread(target=self._run, daemon=True)
        self.task.start()

    def cancel(self):
        self.stop_event.set()
        self.status.set('Cancelling...')

    def _run(self):
        try:
            options = self.task_options
            if options['mode'] == 'live':
                reference, samples = layout_builder.collect_live(
                    config.capture,
                    options['duration'],
                    stop_event=self.stop_event,
                    progress=self._progress
                )
            else:
                self._set_status(
                    f"Reading {len(options['files'])} screenshots..."
                )
                reference, samples = layout_builder.collect_offline(
                    options['files']
                )

            result = layout_builder.build_layout(
                options['routine_name'],
                options['class_name'],
                reference,
                samples,
                dry_run=options['dry_run']
            )
            if result['saved'] and config.routine.path == options['routine_path']:
                config.layout = result['layout']
            action = 'Saved' if result['saved'] else 'Previewed'
            self.events.put(('finish', (
                f"{action} {result['nodes']} nodes from "
                f"{result['platforms']} platforms and "
                f"{result['samples']} standing positions.",
                result['preview_path']
            )))
        except InterruptedError as error:
            self.events.put(('finish', (str(error), None)))
        except Exception as error:
            self.events.put(('finish', (f'Build failed: {error}', None)))

    def _progress(self, elapsed, duration, samples):
        self._set_status(
            f'Live sampling: {elapsed:.0f}/{duration:.0f}s, '
            f'{samples} standing samples. Move around and pause on each platform.'
        )

    def _set_status(self, message):
        self.events.put(('status', message))

    def _process_events(self):
        while True:
            try:
                event, payload = self.events.get_nowait()
            except queue.Empty:
                break
            if event == 'status':
                self.status.set(payload)
            elif event == 'finish':
                self._finish(*payload)
        self.after(100, self._process_events)

    def _finish(self, message, preview_path=None):
        self.status.set(message)
        self.build_button.configure(state=tk.NORMAL)
        self.cancel_button.configure(state=tk.DISABLED)
        if preview_path and os.path.isfile(preview_path):
            resampling = getattr(Image, 'Resampling', Image)
            with Image.open(preview_path) as source:
                image = source.copy()
            image.thumbnail(self.PREVIEW_SIZE, resampling.LANCZOS)
            self.preview_image = ImageTk.PhotoImage(image)
            self.preview.configure(image=self.preview_image, text='')

    def _update_source_state(self):
        live = self.mode.get() == 'live'
        self.duration_input.configure(state=tk.NORMAL if live else tk.DISABLED)
        self.files_button.configure(state=tk.DISABLED if live else tk.NORMAL)
