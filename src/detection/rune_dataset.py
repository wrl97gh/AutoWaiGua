"""
Records rune screenshots and attempt metadata so ground-truth labels can be
added later with tools/rune_labeler.py. Also provides the session-discovery
helpers shared by the labeling and evaluation tools.
"""

import os
import json
import cv2
from datetime import datetime

DATASET_DIR = os.path.join('assets', 'rune_dataset')
LEGACY_DEBUG_DIR = os.path.join('assets', 'debug', 'rune')
DATASET_ROOTS = (DATASET_DIR, LEGACY_DEBUG_DIR)
META_FILE = 'meta.json'
LABEL_FILE = 'label.json'


class RuneDatasetRecorder:
    """
    Collects the screenshots of a single rune attempt. Disk errors are caught
    and reported so that recording can never break the solve loop.
    """

    def __init__(self, engine):
        self.engine = engine
        base = os.path.join(DATASET_DIR, datetime.now().strftime('%Y%m%d_%H%M%S'))
        directory = base
        counter = 1
        while os.path.exists(directory):
            directory = f'{base}_{counter}'
            counter += 1
        self.directory = directory
        self.frames = []

    def add_frame(self, frame, tag):
        if frame is None:
            return
        try:
            os.makedirs(self.directory, exist_ok=True)
            name = f'{len(self.frames):02d}_{tag}.png'
            if cv2.imwrite(os.path.join(self.directory, name), frame):
                self.frames.append(name)
        except Exception as e:
            print(f'[!] Failed to save rune screenshot: {e}')

    def finish(self, solution, panel_gone_after_entry):
        if not self.frames:
            return
        meta = {
            'time': datetime.now().isoformat(timespec='seconds'),
            'engine': self.engine,
            'prediction': list(solution) if solution else None,
            'entered': solution is not None,
            'panel_gone_after_entry': panel_gone_after_entry,
            'frames': self.frames,
        }
        try:
            with open(os.path.join(self.directory, META_FILE), 'w') as file:
                json.dump(meta, file, indent=2)
            print(f'Rune screenshots saved to: {self.directory}')
        except Exception as e:
            print(f'[!] Failed to save rune metadata: {e}')


#################################
#       Session discovery       #
#################################
def list_sessions(roots=DATASET_ROOTS):
    """
    Returns one dict per rune session found under ROOTS, both new-style
    recorder output and legacy debug directories that contain full frames.
    """

    sessions = []
    for root in roots:
        if not os.path.isdir(root):
            continue
        for name in sorted(os.listdir(root)):
            directory = os.path.join(root, name)
            if not os.path.isdir(directory):
                continue
            frames = list_frames(directory)
            if not frames:
                continue
            sessions.append({
                'directory': directory,
                'name': name,
                'frames': frames,
                'meta': read_json(os.path.join(directory, META_FILE)),
                'label': read_json(os.path.join(directory, LABEL_FILE)),
            })
    return sessions


def list_frames(directory):
    """Returns the full-frame screenshots in DIRECTORY, panel frames first."""

    names = sorted(os.listdir(directory))
    recorded = [n for n in names if n.endswith('_panel.png') or n.endswith('_after_entry.png')]
    if recorded:
        return recorded
    return [n for n in names if n.endswith('_01_frame.png')]


def panel_frames(frames):
    """Filters FRAMES down to the ones that should show the rune panel."""

    panels = [n for n in frames if n.endswith('_panel.png')]
    if panels:
        return panels
    return [n for n in frames if not n.endswith('_after_entry.png')]


def read_json(path):
    try:
        with open(path, 'r') as file:
            return json.load(file)
    except (OSError, ValueError):
        return None


def write_label(directory, arrows, skipped, source_frame):
    label = {
        'arrows': list(arrows) if arrows else None,
        'skipped': skipped,
        'labeled_at': datetime.now().isoformat(timespec='seconds'),
        'source_frame': source_frame,
    }
    with open(os.path.join(directory, LABEL_FILE), 'w') as file:
        json.dump(label, file, indent=2)
    return label


def clear_label(directory):
    path = os.path.join(directory, LABEL_FILE)
    if os.path.isfile(path):
        os.remove(path)
