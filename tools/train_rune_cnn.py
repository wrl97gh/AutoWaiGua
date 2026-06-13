"""
Trains a small CNN arrow classifier from the labeled rune dataset, as a
lightweight replacement for the Faster R-CNN detection pipeline.

Usage:
    python3 tools/train_rune_cnn.py                  # extract + train + evaluate
    python3 tools/train_rune_cnn.py --rebuild-cache  # re-extract crops from frames
    python3 tools/train_rune_cnn.py --epochs 60

Only sessions labeled with tools/rune_labeler.py are used; skipped and
unlabeled sessions are ignored. Frames are gated by the rune-panel visibility
check so junk frames inside labeled sessions don't poison the labels.
Train/validation are split by session so near-duplicate frames cannot leak.
"""

import os
import sys
import json
import argparse
import random

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT)
os.chdir(PROJECT)

import cv2
import numpy as np

CLASSES = ['up', 'down', 'left', 'right']
INPUT_SIZE = 64
SLOT_OVERLAP_RATIO = 0.12       # Same slot geometry the live detector will use
CACHE_PATH = os.path.join('assets', 'models', 'rune_cnn_data.npz')
MODEL_PATH = os.path.join('assets', 'models', 'rune_arrow_cnn.keras')
META_PATH = os.path.join('assets', 'models', 'rune_arrow_cnn.json')
VAL_FRACTION = 0.15
SEED = 7


def split_slots(arrow_roi):
    height, width = arrow_roi.shape[:2]
    slot_width = width / 4
    overlap = slot_width * SLOT_OVERLAP_RATIO
    slots = []
    for i in range(4):
        left = max(0, round(i * slot_width - overlap))
        right = min(width, round((i + 1) * slot_width + overlap))
        slots.append(arrow_roi[:, left:right])
    return slots


def slot_to_input(slot):
    return cv2.resize(slot[:, :, :3], (INPUT_SIZE, INPUT_SIZE), interpolation=cv2.INTER_AREA)


def extract_dataset():
    from src.detection import rune_dataset, rune_roi, detection

    sessions = [s for s in rune_dataset.list_sessions()
                if s['label'] and s['label'].get('arrows')]
    print(f'{len(sessions)} labeled sessions')

    images, labels, session_ids = [], [], []
    dropped = 0
    for sid, sess in enumerate(sessions):
        arrows = sess['label']['arrows']
        for name in rune_dataset.panel_frames(sess['frames']):
            frame = cv2.imread(os.path.join(sess['directory'], name))
            if frame is None:
                continue
            if not detection.find_rune_panel(frame):
                dropped += 1
                continue
            roi = rune_roi.extract_arrow_roi(frame)
            if roi.size == 0:
                continue
            for slot, arrow in zip(split_slots(roi), arrows):
                images.append(slot_to_input(slot))
                labels.append(CLASSES.index(arrow))
                session_ids.append(sid)

    images = np.array(images, dtype=np.uint8)
    labels = np.array(labels, dtype=np.int64)
    session_ids = np.array(session_ids, dtype=np.int64)
    print(f'extracted {len(images)} arrow crops '
          f'({dropped} frames dropped by the panel-visibility gate)')
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    np.savez_compressed(CACHE_PATH, images=images, labels=labels, session_ids=session_ids)
    return images, labels, session_ids


def load_dataset(rebuild):
    if not rebuild and os.path.isfile(CACHE_PATH):
        data = np.load(CACHE_PATH)
        print(f'loaded cache: {len(data["images"])} crops')
        return data['images'], data['labels'], data['session_ids']
    return extract_dataset()


def main():
    parser = argparse.ArgumentParser(description='Train the rune arrow CNN.')
    parser.add_argument('--rebuild-cache', action='store_true')
    parser.add_argument('--epochs', type=int, default=40)
    parser.add_argument('--batch', type=int, default=64)
    args = parser.parse_args()

    images, labels, session_ids = load_dataset(args.rebuild_cache)

    # Split by session so near-identical frames never straddle the split
    rng = random.Random(SEED)
    sessions = sorted(set(session_ids.tolist()))
    rng.shuffle(sessions)
    val_sessions = set(sessions[:max(1, round(len(sessions) * VAL_FRACTION))])
    val_mask = np.isin(session_ids, list(val_sessions))
    x_train, y_train = images[~val_mask], labels[~val_mask]
    x_val, y_val = images[val_mask], labels[val_mask]
    val_session_ids = session_ids[val_mask]
    print(f'train: {len(x_train)} crops / {len(sessions) - len(val_sessions)} sessions | '
          f'val: {len(x_val)} crops / {len(val_sessions)} sessions')

    import tensorflow as tf
    from tensorflow import keras
    from tensorflow.keras import layers
    tf.keras.utils.set_random_seed(SEED)

    model = keras.Sequential([
        layers.Input((INPUT_SIZE, INPUT_SIZE, 3)),
        layers.Rescaling(1.0 / 255),
        layers.Conv2D(16, 3, padding='same', activation='relu'),
        layers.MaxPooling2D(),
        layers.Conv2D(32, 3, padding='same', activation='relu'),
        layers.MaxPooling2D(),
        layers.Conv2D(64, 3, padding='same', activation='relu'),
        layers.MaxPooling2D(),
        layers.Conv2D(64, 3, padding='same', activation='relu'),
        layers.GlobalAveragePooling2D(),
        layers.Dropout(0.3),
        layers.Dense(64, activation='relu'),
        layers.Dense(len(CLASSES)),
    ])
    model.compile(
        optimizer=keras.optimizers.Adam(1e-3),
        loss=keras.losses.SparseCategoricalCrossentropy(from_logits=True),
        metrics=['accuracy'],
    )
    model.summary(line_length=80)

    augment = keras.Sequential([
        layers.RandomTranslation(0.06, 0.06, fill_mode='constant'),
        layers.RandomZoom(0.08, fill_mode='constant'),
        layers.RandomBrightness(0.15),
        layers.RandomContrast(0.2),
    ])

    def train_map(x, y):
        x = augment(x, training=True)
        x = tf.image.random_hue(x / 255.0, 0.45) * 255.0
        return x, y

    train_ds = (tf.data.Dataset.from_tensor_slices((x_train.astype('float32'), y_train))
                .shuffle(len(x_train), seed=SEED)
                .batch(args.batch)
                .map(train_map, num_parallel_calls=tf.data.AUTOTUNE)
                .prefetch(tf.data.AUTOTUNE))
    val_ds = (tf.data.Dataset.from_tensor_slices((x_val.astype('float32'), y_val))
              .batch(args.batch).prefetch(tf.data.AUTOTUNE))

    model.fit(
        train_ds,
        validation_data=val_ds,
        epochs=args.epochs,
        callbacks=[
            keras.callbacks.EarlyStopping(monitor='val_accuracy', patience=8,
                                          restore_best_weights=True),
            keras.callbacks.ReduceLROnPlateau(monitor='val_loss', patience=4, factor=0.5),
        ],
        verbose=2,
    )

    # Per-arrow accuracy, confusion matrix, and full-rune (4/4) accuracy
    logits = model.predict(x_val.astype('float32'), batch_size=256, verbose=0)
    predictions = logits.argmax(axis=1)
    accuracy = (predictions == y_val).mean()
    confusion = np.zeros((4, 4), dtype=int)
    for t, p in zip(y_val, predictions):
        confusion[t][p] += 1
    print(f'\nval per-arrow accuracy: {accuracy:.4f}')
    print('confusion (rows=truth, cols=pred, order up/down/left/right):')
    print(confusion)

    correct_frames = total_frames = 0
    for sid in set(val_session_ids.tolist()):
        idx = np.where(val_session_ids == sid)[0]
        for start in range(0, len(idx), 4):
            quad = idx[start:start + 4]
            if len(quad) < 4:
                continue
            total_frames += 1
            correct_frames += bool((predictions[quad] == y_val[quad]).all())
    print(f'full-rune accuracy (all 4 arrows right, per frame): '
          f'{correct_frames}/{total_frames} = {correct_frames / total_frames:.4f}')

    import time
    batch = x_val[:4].astype('float32')
    model.predict(batch, verbose=0)
    t0 = time.perf_counter()
    for _ in range(50):
        model.predict(batch, verbose=0)
    latency = (time.perf_counter() - t0) / 50 * 1000
    print(f'inference latency (4 slots in one batch): {latency:.1f} ms')

    model.save(MODEL_PATH)
    with open(META_PATH, 'w') as file:
        json.dump({
            'classes': CLASSES,
            'input_size': INPUT_SIZE,
            'slot_overlap_ratio': SLOT_OVERLAP_RATIO,
            'val_arrow_accuracy': round(float(accuracy), 4),
            'val_full_rune_accuracy': round(correct_frames / total_frames, 4),
            'train_crops': int(len(x_train)),
            'val_crops': int(len(x_val)),
        }, file, indent=2)
    print(f'saved {MODEL_PATH} and {META_PATH}')


if __name__ == '__main__':
    main()
