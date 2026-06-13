"""
CNN-based rune arrow classifier (detection engine 3).

A drop-in alternative to detection.py / detection2.py that exposes the same
interface (find_rune_panel / detect_rune_slots / merge_detection) but replaces
the Faster R-CNN pipeline with the small per-slot CNN trained by
tools/train_rune_cnn.py. It splits the rune panel into four slots exactly the
way the trainer did, runs all four through the CNN in a single batch, and
returns one direction per slot.

The CNN is loaded lazily and cached, so importing this module is cheap and the
model is only read when the engine is actually used.
"""

import os
import json
import cv2
import numpy as np
from src.detection import detection, rune_roi

MODEL_PATH = os.path.join('assets', 'models', 'rune_arrow_cnn.keras')
META_PATH = os.path.join('assets', 'models', 'rune_arrow_cnn.json')

# Below this softmax confidence a slot is treated as uncertain (None) so the
# bot's multi-frame voting keeps collecting frames instead of guessing.
SLOT_CONFIDENCE = 0.5

_model = None
_classes = ['up', 'down', 'left', 'right']
_input_size = 64
_slot_overlap = 0.12
_load_error = None


def available():
    """Returns True if the trained CNN model file is present."""

    return os.path.isfile(MODEL_PATH)


def _load():
    """Lazily loads and caches the CNN. Returns None if it cannot be loaded."""

    global _model, _classes, _input_size, _slot_overlap, _load_error
    if _model is not None or _load_error is not None:
        return _model
    try:
        if os.path.isfile(META_PATH):
            with open(META_PATH) as file:
                meta = json.load(file)
            _classes = meta.get('classes', _classes)
            _input_size = meta.get('input_size', _input_size)
            _slot_overlap = meta.get('slot_overlap_ratio', _slot_overlap)
        import keras
        _model = keras.models.load_model(MODEL_PATH)
    except Exception as exc:        # Missing/corrupt model: disable this engine
        _load_error = exc
        print(f'[!] Could not load rune CNN ({MODEL_PATH}): {exc}')
    return _model


def _split_slots(arrow_roi):
    height, width = arrow_roi.shape[:2]
    slot_width = width / 4
    overlap = slot_width * _slot_overlap
    slots = []
    for i in range(4):
        left = max(0, round(i * slot_width - overlap))
        right = min(width, round((i + 1) * slot_width + overlap))
        slots.append(arrow_roi[:, left:right])
    return slots


def _preprocess(slot):
    # Must match tools/train_rune_cnn.slot_to_input exactly: BGR (first three
    # channels, dropping any alpha), resized to the model's input size.
    return cv2.resize(slot[:, :, :3], (_input_size, _input_size), interpolation=cv2.INTER_AREA)


def find_rune_panel(image, debug_dir=None, debug_prefix=''):
    """Engine-agnostic colour gate; reused from detection.py."""

    return detection.find_rune_panel(image, debug_dir=debug_dir, debug_prefix=debug_prefix)


def detect_rune_slots(model, image, debug_dir=None, debug_prefix=''):
    """
    Classifies the four rune arrows. Returns a four-item list of directions
    (or None for an uncertain slot), or None when the panel is not visible.
    The MODEL argument is ignored; the CNN is loaded internally.
    """

    arrow_roi = rune_roi.extract_arrow_roi(image)
    if arrow_roi is None or arrow_roi.size == 0:
        return None
    if not detection.find_rune_panel(image):
        return None
    net = _load()
    if net is None:
        return None

    slots = _split_slots(arrow_roi)
    batch = np.stack([_preprocess(s) for s in slots]).astype('float32')
    logits = net(batch, training=False).numpy()
    probs = _softmax(logits)

    result = []
    confidences = []
    for row in probs:
        idx = int(row.argmax())
        conf = float(row[idx])
        confidences.append(conf)
        result.append(_classes[idx] if conf >= SLOT_CONFIDENCE else None)
    detection._save_debug_image(debug_dir, f'{debug_prefix}arrow_roi.png', arrow_roi)
    detection._save_debug_text(
        debug_dir, 'debug.txt',
        f'{debug_prefix}cnn: {result} conf={[round(c, 3) for c in confidences]}')
    return result


def merge_detection(model, image, debug_dir=None, debug_prefix=''):
    """Returns the four directions only when every slot is confident, else []."""

    slots = detect_rune_slots(model, image, debug_dir=debug_dir, debug_prefix=debug_prefix)
    if slots and all(slots):
        return slots
    return []


def _softmax(logits):
    shifted = logits - logits.max(axis=1, keepdims=True)
    exp = np.exp(shifted)
    return exp / exp.sum(axis=1, keepdims=True)
