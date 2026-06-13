"""Builds pathfinding layouts from live or saved minimap screenshots."""

import glob
import os
import pickle
import time
from collections import defaultdict

import cv2
import numpy as np

from src.common import config, utils
from src.routine.layout import Layout


MIN_SEGMENT_PX = 6
NODE_SPACING_PX = 6
FOOT_ROWS = (2, 7)
FOOT_HALF_WIDTH = 3
BIN_Q = (10, 40, 40)


def calibrate_minimap(frame):
    from src.modules import capture as cap

    tl, _ = cap.Capture._single_match(frame, cap.MM_TL_TEMPLATE)
    _, br = cap.Capture._single_match(frame, cap.MM_BR_TEMPLATE)
    mm_tl = (tl[0] + cap.MINIMAP_BOTTOM_BORDER,
             tl[1] + cap.MINIMAP_TOP_BORDER)
    mm_br = (max(mm_tl[0] + 1, br[0] - cap.MINIMAP_BOTTOM_BORDER),
             max(mm_tl[1] + 1, br[1] - cap.MINIMAP_BOTTOM_BORDER))
    return mm_tl, mm_br


def find_player(minimap, capture=None):
    from src.modules import capture as cap

    template = cap.PLAYER_TEMPLATE
    capture = capture or config.capture
    if capture is not None and hasattr(capture, 'scale_minimap_template'):
        template = capture.scale_minimap_template(template)
    matches = utils.multi_match(minimap, template, threshold=0.8)
    return matches[0] if matches else None


def foot_bins(minimap_hsv, player):
    height, width = minimap_hsv.shape[:2]
    px, py = player
    bins = set()
    for dy in range(*FOOT_ROWS):
        y = py + dy
        if not 0 <= y < height:
            continue
        for dx in range(-FOOT_HALF_WIDTH, FOOT_HALF_WIDTH + 1):
            x = px + dx
            if not 0 <= x < width:
                continue
            h, s, v = minimap_hsv[y, x]
            if 20 <= h <= 40 and s > 140 and v > 150:
                continue
            bins.add((h // BIN_Q[0], s // BIN_Q[1], v // BIN_Q[2]))
    return bins


def build_color_model(samples, reference):
    counts = defaultdict(int)
    for bins in samples:
        for value in bins:
            counts[value] += 1
    threshold = max(2, round(0.15 * len(samples)))
    model = {value for value, count in counts.items() if count >= threshold}

    hsv = cv2.cvtColor(reference, cv2.COLOR_BGR2HSV)
    h = hsv[:, :, 0] // BIN_Q[0]
    s = hsv[:, :, 1] // BIN_Q[1]
    v = hsv[:, :, 2] // BIN_Q[2]
    total = h.size
    kept = set()
    for value in model:
        share = np.count_nonzero(
            (h == value[0]) & (s == value[1]) & (v == value[2])
        ) / total
        if share <= 0.06:
            kept.add(value)
    return kept


def platform_mask(minimap, model):
    hsv = cv2.cvtColor(minimap, cv2.COLOR_BGR2HSV)
    h = hsv[:, :, 0] // BIN_Q[0]
    s = hsv[:, :, 1] // BIN_Q[1]
    v = hsv[:, :, 2] // BIN_Q[2]
    mask = np.zeros(minimap.shape[:2], dtype=bool)
    for bh, bs, bv in model:
        mask |= (h == bh) & (s == bs) & (v == bv)
    return mask


def mask_icons(mask, minimap):
    player = find_player(minimap)
    if player:
        cv2.circle(mask, player, 6, False, -1)

    from src.modules.notifier import PORTAL_RANGES, PORTAL_TEMPLATE

    filtered = utils.filter_color(minimap, PORTAL_RANGES)
    portal_template = PORTAL_TEMPLATE
    capture = config.capture
    if capture is not None and hasattr(capture, 'scale_minimap_template'):
        portal_template = capture.scale_minimap_template(portal_template)
    for x, y in utils.multi_match(filtered, portal_template, threshold=0.8):
        cv2.circle(mask, (x, y), 9, False, -1)
    return mask


def extract_platforms(mask):
    height, width = mask.shape
    segments = []
    for y in range(height):
        x = 0
        while x < width:
            if mask[y, x]:
                x0 = x
                while x < width and mask[y, x]:
                    x += 1
                if x - x0 >= MIN_SEGMENT_PX:
                    segments.append([x0, x - 1, y])
            else:
                x += 1

    merged = []
    for segment in sorted(segments, key=lambda value: (value[2], value[0])):
        for existing in merged:
            overlaps = not (
                segment[1] < existing[0] - 3
                or segment[0] > existing[1] + 3
            )
            if abs(segment[2] - existing[2]) <= 2 and overlaps:
                existing[0] = min(existing[0], segment[0])
                existing[1] = max(existing[1], segment[1])
                break
        else:
            merged.append(list(segment))

    kept = []
    for x0, x1, y in merged:
        if y >= 2:
            above = mask[max(0, y - 3):y - 1, x0:x1 + 1]
            if above.size and np.count_nonzero(above) / above.size > 0.5:
                continue
        if x1 - x0 >= MIN_SEGMENT_PX:
            kept.append([x0, x1, y])
    return kept


def collect_offline(paths):
    if isinstance(paths, str):
        paths = sorted(glob.glob(paths))
    else:
        paths = sorted(paths)
    if not paths:
        raise ValueError('No screenshots were selected.')

    first = cv2.imread(paths[0])
    if first is None:
        raise ValueError(f'Could not read screenshot: {paths[0]}')
    mm_tl, mm_br = calibrate_minimap(first)
    samples = []
    reference = None
    for path in paths:
        frame = cv2.imread(path)
        if frame is None:
            continue
        minimap = frame[mm_tl[1]:mm_br[1], mm_tl[0]:mm_br[0]]
        if minimap.size == 0:
            continue
        player = find_player(minimap)
        if player is not None:
            reference = minimap.copy()
            samples.append((reference, player))
    return reference, samples


def collect_live(capture, duration, stop_event=None, progress=None):
    samples = []
    reference = None
    last_pos = None
    stable_since = 0
    started = time.time()
    end = started + duration

    while time.time() < end:
        if stop_event is not None and stop_event.is_set():
            raise InterruptedError('Layout build cancelled.')
        time.sleep(0.2)
        info = capture.minimap
        minimap = info.get('minimap') if info else None
        if minimap is None or minimap.size == 0:
            continue
        minimap = minimap.copy()
        player = find_player(minimap, capture=capture)
        if player is None:
            continue
        if last_pos and utils.distance(player, last_pos) < 3:
            if stable_since and time.time() - stable_since > 0.4:
                reference = minimap
                samples.append((reference, player))
                stable_since = time.time() + 1.0
            elif not stable_since:
                stable_since = time.time()
        else:
            stable_since = 0
        last_pos = player
        if progress:
            progress(time.time() - started, duration, len(samples))
    return reference, samples


def build_layout(name, class_name, reference, samples, out_dir=None,
                 dry_run=False):
    distinct = {}
    for minimap, player in samples:
        key = (player[0] // 4, player[1] // 4)
        distinct.setdefault(key, (minimap, player))
    samples = list(distinct.values())
    if reference is None or len(samples) < 3:
        raise ValueError(
            'Not enough distinct standing spots to calibrate (need at least 3).'
        )

    bin_sets = [
        foot_bins(cv2.cvtColor(minimap, cv2.COLOR_BGR2HSV), player)
        for minimap, player in samples
    ]
    model = build_color_model(bin_sets, reference)
    mask = platform_mask(reference, model).astype(np.uint8)
    mask = mask_icons(mask, reference).astype(bool)
    platforms = extract_platforms(mask)
    if not platforms:
        raise ValueError(
            'No platforms found. Collect more standing positions and try again.'
        )

    out_dir = out_dir or os.path.join(
        config.RESOURCES_DIR, 'layouts', class_name
    )
    out_path = os.path.join(out_dir, name)
    if os.path.isfile(out_path):
        with open(out_path, 'rb') as file:
            layout = pickle.load(file)
    else:
        layout = Layout(name)

    nodes = []
    for x0, x1, y in platforms:
        for x in range(x0 + 2, x1 - 1, NODE_SPACING_PX):
            nodes.append((x, y))
        nodes.append((x1 - 1, y))

    width = reference.shape[1]
    for x, y in nodes:
        layout.add(x / width, y / width, force=True)

    preview = reference.copy()
    for x0, x1, y in platforms:
        cv2.line(preview, (x0, y), (x1, y), (0, 0, 255), 1)
    for x, y in nodes:
        cv2.circle(preview, (x, y), 1, (255, 165, 0), -1)

    debug_dir = os.path.join('assets', 'debug')
    os.makedirs(debug_dir, exist_ok=True)
    preview_path = os.path.join(debug_dir, f'layout_preview_{name}.png')
    cv2.imwrite(
        preview_path,
        cv2.resize(preview, None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST)
    )

    total = len(layout.search(0, 5, 0, 5))
    if not dry_run:
        os.makedirs(out_dir, exist_ok=True)
        with open(out_path, 'wb') as file:
            pickle.dump(layout, file)

    return {
        'layout': layout,
        'nodes': total,
        'platforms': len(platforms),
        'samples': len(samples),
        'preview_path': preview_path,
        'out_path': out_path,
        'saved': not dry_run
    }
