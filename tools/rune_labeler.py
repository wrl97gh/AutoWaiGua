"""
Tkinter tool for labeling rune screenshots with ground-truth arrows.

Usage:
    python3 tools/rune_labeler.py            # launch the labeling UI
    python3 tools/rune_labeler.py --stats    # print labeling progress and exit

Keys:
    Up/Down/Left/Right  append an arrow to the label
    BackSpace           remove the last arrow
    Enter               save the 4-arrow label, then jump to the next unlabeled
    s                   mark this session as skipped (no usable rune panel)
    c                   clear this session's saved label
    n / p               next / previous session
    , / .               previous / next frame within the session
    f                   toggle between the arrow-region crop and the full frame
    g                   jump to the next unlabeled session
    q                   quit
"""

import os
import sys
import argparse

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT)
os.chdir(PROJECT)

import cv2
from src.detection import rune_roi, rune_dataset

ARROW_GLYPHS = {'up': '↑', 'down': '↓', 'left': '←', 'right': '→'}
DISPLAY_WIDTH = 880


def arrows_text(arrows):
    if not arrows:
        return '(empty)'
    return '  '.join(ARROW_GLYPHS.get(a, '?') for a in arrows)


def print_stats(sessions):
    labeled = sum(1 for s in sessions if s['label'] and s['label'].get('arrows'))
    skipped = sum(1 for s in sessions if s['label'] and s['label'].get('skipped'))
    print(f"Sessions: {len(sessions)} total | {labeled} labeled | "
          f"{skipped} skipped | {len(sessions) - labeled - skipped} unlabeled")


class Labeler:
    def __init__(self, sessions):
        import tkinter as tk
        self.tk = tk
        self.sessions = sessions
        self.index = 0
        self.frame_index = 0
        self.entry = []
        self.show_full = False
        self.message = ''
        self.photo = None       # Keep a reference so Tk doesn't drop the image

        self.root = tk.Tk()
        self.root.title('Rune Labeler')
        self.header = tk.Label(self.root, font=('TkDefaultFont', 14, 'bold'))
        self.header.pack(pady=(10, 2))
        self.sub_header = tk.Label(self.root, fg='gray')
        self.sub_header.pack()
        self.image_label = tk.Label(self.root)
        self.image_label.pack(padx=10, pady=8)
        self.entry_label = tk.Label(self.root, font=('TkDefaultFont', 28))
        self.entry_label.pack()
        self.info_label = tk.Label(self.root, fg='gray')
        self.info_label.pack()
        self.status_label = tk.Label(self.root, fg='gray')
        self.status_label.pack(pady=(2, 0))
        self.help_label = tk.Label(
            self.root,
            fg='gray',
            text='arrows: label   Enter: save   BackSpace: undo   s: skip   c: clear   '
                 'n/p: session   ,/.: frame   f: full frame   g: next unlabeled   q: quit'
        )
        self.help_label.pack(pady=(2, 10))

        for key in ('Up', 'Down', 'Left', 'Right'):
            self.root.bind(f'<{key}>', lambda e, k=key.lower(): self.add_arrow(k))
        self.root.bind('<BackSpace>', lambda e: self.undo_arrow())
        self.root.bind('<Return>', lambda e: self.save_label())
        self.root.bind('s', lambda e: self.skip_session())
        self.root.bind('c', lambda e: self.clear_label())
        self.root.bind('n', lambda e: self.move(1))
        self.root.bind('p', lambda e: self.move(-1))
        self.root.bind(',', lambda e: self.move_frame(-1))
        self.root.bind('.', lambda e: self.move_frame(1))
        self.root.bind('f', lambda e: self.toggle_full())
        self.root.bind('g', lambda e: self.jump_to_unlabeled())
        self.root.bind('q', lambda e: self.root.destroy())

        if not self.is_unlabeled(self.sessions[0]):
            self.jump_to_unlabeled()
        self.refresh()

    @staticmethod
    def is_unlabeled(session):
        return session['label'] is None

    def session(self):
        return self.sessions[self.index]

    def add_arrow(self, direction):
        if len(self.entry) < 4:
            self.entry.append(direction)
            self.message = ''
        self.refresh(reload_image=False)

    def undo_arrow(self):
        if self.entry:
            self.entry.pop()
        self.refresh(reload_image=False)

    def save_label(self):
        if len(self.entry) != 4:
            self.message = 'Need exactly 4 arrows before saving'
            self.refresh(reload_image=False)
            return
        sess = self.session()
        source = sess['frames'][self.frame_index]
        sess['label'] = rune_dataset.write_label(sess['directory'], self.entry, False, source)
        self.entry = []
        self.message = f"Saved {sess['name']}"
        self.jump_to_unlabeled()

    def skip_session(self):
        sess = self.session()
        sess['label'] = rune_dataset.write_label(sess['directory'], None, True, None)
        self.entry = []
        self.message = f"Skipped {sess['name']}"
        self.jump_to_unlabeled()

    def clear_label(self):
        sess = self.session()
        rune_dataset.clear_label(sess['directory'])
        sess['label'] = None
        self.entry = []
        self.message = f"Cleared label of {sess['name']}"
        self.refresh(reload_image=False)

    def move(self, step):
        self.index = (self.index + step) % len(self.sessions)
        self.frame_index = 0
        self.entry = []
        self.message = ''
        self.refresh()

    def move_frame(self, step):
        frames = self.session()['frames']
        self.frame_index = (self.frame_index + step) % len(frames)
        self.refresh()

    def toggle_full(self):
        self.show_full = not self.show_full
        self.refresh()

    def jump_to_unlabeled(self):
        start = self.index
        for offset in range(1, len(self.sessions) + 1):
            i = (start + offset) % len(self.sessions)
            if self.is_unlabeled(self.sessions[i]):
                self.index = i
                self.frame_index = 0
                self.refresh()
                return
        self.message = 'All sessions are labeled!'
        self.refresh()

    def refresh(self, reload_image=True):
        sess = self.session()
        if reload_image:
            self.photo = self._render_frame(sess)
            self.image_label.config(image=self.photo, text='' if self.photo else 'Could not load image')

        label = sess['label']
        if label is None:
            state = 'UNLABELED'
        elif label.get('skipped'):
            state = 'SKIPPED'
        else:
            state = 'labeled: ' + arrows_text(label.get('arrows'))
        self.header.config(text=f"[{self.index + 1}/{len(self.sessions)}] {sess['name']}  ({state})")

        frame_name = sess['frames'][self.frame_index]
        view = 'full frame' if self.show_full else 'arrow region'
        self.sub_header.config(
            text=f"frame {self.frame_index + 1}/{len(sess['frames'])}: {frame_name}  ({view})"
        )

        self.entry_label.config(text=arrows_text(self.entry))

        info = []
        meta = sess['meta']
        if meta:
            prediction = meta.get('prediction')
            info.append(f"engine {meta.get('engine')}: "
                        f"{arrows_text(prediction) if prediction else 'no answer'}")
            gone = meta.get('panel_gone_after_entry')
            if gone is not None:
                info.append(f"panel gone after entry: {'yes' if gone else 'no'}")
            if label and label.get('arrows') and prediction:
                info.append('MATCH' if label['arrows'] == prediction else 'MISMATCH')
        self.info_label.config(text='  |  '.join(info))

        labeled = sum(1 for s in self.sessions if s['label'] and s['label'].get('arrows'))
        skipped = sum(1 for s in self.sessions if s['label'] and s['label'].get('skipped'))
        unlabeled = len(self.sessions) - labeled - skipped
        progress = f'progress: {labeled} labeled · {skipped} skipped · {unlabeled} left'
        self.status_label.config(
            text=f'{self.message}    {progress}' if self.message else progress
        )

    def _render_frame(self, sess):
        from PIL import Image, ImageTk
        path = os.path.join(sess['directory'], sess['frames'][self.frame_index])
        image = cv2.imread(path, cv2.IMREAD_UNCHANGED)
        if image is None:
            return None
        if not self.show_full:
            roi = rune_roi.extract_arrow_roi(image)
            if roi.size > 0:
                image = roi
        code = cv2.COLOR_BGRA2RGB if image.shape[2] == 4 else cv2.COLOR_BGR2RGB
        image = cv2.cvtColor(image, code)
        scale = DISPLAY_WIDTH / image.shape[1]
        image = cv2.resize(
            image,
            (DISPLAY_WIDTH, max(1, round(image.shape[0] * scale))),
            interpolation=cv2.INTER_CUBIC if scale > 1 else cv2.INTER_AREA
        )
        return ImageTk.PhotoImage(Image.fromarray(image))

    def run(self):
        self.root.mainloop()


def main():
    parser = argparse.ArgumentParser(description='Label rune screenshots with ground truth.')
    parser.add_argument('--stats', action='store_true', help='print labeling progress and exit')
    args = parser.parse_args()

    sessions = rune_dataset.list_sessions()
    if not sessions:
        print('No rune sessions found under assets/rune_dataset or assets/debug/rune.')
        return
    if args.stats:
        print_stats(sessions)
        return
    Labeler(sessions).run()


if __name__ == '__main__':
    main()
