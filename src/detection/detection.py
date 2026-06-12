"""A module for classifying directional arrows using TensorFlow."""

import cv2
import os
import tensorflow as tf
import numpy as np
from src.common import utils
from src.detection import rune_roi

MODEL_DIR = 'assets/models/rune_model_rnn_filtered_cannied/saved_model'
REQUIRED_MODEL_FILES = (
    'saved_model.pb',
    os.path.join('variables', 'variables.index'),
    os.path.join('variables', 'variables.data-00000-of-00001'),
)
DEFAULT_ARROW_HSV_RANGES = (
    ((35, 140, 130), (75, 255, 255)),
)
GREEN_ARROW_HSV_RANGES = DEFAULT_ARROW_HSV_RANGES
CYAN_ARROW_HSV_RANGES = (
    ((85, 120, 120), (118, 255, 255)),
)
RED_ARROW_HSV_RANGES = (
    ((0, 120, 120), (12, 255, 255)),
    ((165, 120, 120), (179, 255, 255)),
)
YELLOW_ARROW_HSV_RANGES = (
    ((18, 120, 120), (38, 255, 255)),
)
BROAD_ARROW_HSV_RANGES = (
    ((0, 110, 110), (75, 255, 255)),
    ((85, 140, 130), (118, 255, 255)),
    ((145, 140, 130), (179, 255, 255)),
)
ARROW_HSV_PROFILES = (
    ('green', GREEN_ARROW_HSV_RANGES),
    ('cyan', CYAN_ARROW_HSV_RANGES),
    ('red', RED_ARROW_HSV_RANGES),
    ('yellow', YELLOW_ARROW_HSV_RANGES),
    ('broad', BROAD_ARROW_HSV_RANGES),
)
SLOT_ARROW_HSV_PROFILES = (
    ('broad', BROAD_ARROW_HSV_RANGES),
)
MIN_ARROW_MASK_RATIO = 0.003
MAX_ARROW_MASK_RATIO = 0.12
MIN_SLOT_MASK_RATIO = 0.002
MAX_SLOT_MASK_RATIO = 0.2
MAX_BROAD_SLOT_MASK_RATIO = 0.22
SLOT_EARLY_ACCEPT_SCORE = 0.35
SLOT_OVERLAP_RATIO = 0.12
RUNE_PANEL_BLUE_RANGES = (
    ((88, 30, 70), (130, 170, 220)),
)
RUNE_PANEL_BORDER_RANGES = (
    ((18, 80, 120), (42, 255, 255)),
)
MIN_RUNE_PANEL_BLUE_RATIO = 0.3
MIN_RUNE_PANEL_BORDER_RATIO = 0.006
STRONG_RUNE_PANEL_BORDER_RATIO = 0.02
MODEL_PAD_HEIGHT = 384
MODEL_PAD_WIDTH = 455


#########################
#       Functions       #
#########################
def load_model():
    """
    Loads the saved model's weights into an Tensorflow model.
    :return:    The Tensorflow model object.
    """

    missing = [
        os.path.join(MODEL_DIR, file)
        for file in REQUIRED_MODEL_FILES
        if not os.path.isfile(os.path.join(MODEL_DIR, file))
    ]
    if missing:
        raise FileNotFoundError(
            'Rune TensorFlow model is incomplete. Missing:\n'
            + '\n'.join(f'  - {file}' for file in missing)
            + '\nDownload/extract the full models folder into assets/models, then restart Auto Maple.'
        )
    return tf.saved_model.load(MODEL_DIR)


def canny(image):
    """
    Performs Canny edge detection on IMAGE.
    :param image:   The input image as a Numpy array.
    :return:        The edges in IMAGE.
    """

    image = cv2.Canny(image, 200, 300)
    colored = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    return colored


def filter_color(image, ranges=None):
    """
    Filters out all colors not between orange and green on the HSV scale, which
    eliminates some noise around the arrows.
    :param image:   The input image.
    :param ranges:  Optional HSV ranges to keep.
    :return:        The color-filtered image.
    """

    return _mask_image(image, _color_mask(image, ranges))


def _color_mask(image, ranges=None):
    if ranges is None:
        ranges = DEFAULT_ARROW_HSV_RANGES
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, ranges[0][0], ranges[0][1])
    for lower, upper in ranges[1:]:
        mask = cv2.bitwise_or(mask, cv2.inRange(hsv, lower, upper))
    return mask


def _mask_image(image, mask):
    return cv2.bitwise_and(image, image, mask=mask)


def _arrow_hsv_profiles():
    return ARROW_HSV_PROFILES


def _slot_hsv_profiles():
    return SLOT_ARROW_HSV_PROFILES


def _extract_rune_arrow_roi(image, debug_dir=None, debug_prefix=''):
    cropped = rune_roi.crop_screen_region(image)
    _save_debug_image(debug_dir, f'{debug_prefix}01_frame.png', image)
    _save_debug_image(debug_dir, f'{debug_prefix}02_cropped.png', cropped)
    if cropped.size == 0:
        _save_debug_text(debug_dir, 'debug.txt', f'{debug_prefix}cropped image is empty')
        return None, None

    arrow_roi = rune_roi.crop_arrow_region(cropped)
    _save_debug_image(debug_dir, f'{debug_prefix}02_arrow_roi.png', arrow_roi)
    if arrow_roi.size == 0:
        _save_debug_text(debug_dir, 'debug.txt', f'{debug_prefix}arrow roi is empty')
        return cropped, None
    return cropped, arrow_roi


def _mask_ratio(mask):
    return np.count_nonzero(mask) / mask.size if mask.size else 0


def find_rune_panel(image, debug_dir=None, debug_prefix=''):
    """
    Returns True when the rune input panel is visible in IMAGE.
    """

    _, arrow_roi = _extract_rune_arrow_roi(image, debug_dir=debug_dir, debug_prefix=debug_prefix)
    if arrow_roi is None:
        return False
    visible, metrics = _rune_panel_visible(arrow_roi)
    _save_debug_text(
        debug_dir,
        'debug.txt',
        f"{debug_prefix}panel blue={metrics['blue']:.4f} "
        f"border={metrics['border']:.4f} visible={visible}"
    )
    return visible


def _rune_panel_visible(arrow_roi):
    blue = _mask_ratio(_color_mask(arrow_roi, RUNE_PANEL_BLUE_RANGES))
    border = _mask_ratio(_color_mask(arrow_roi, RUNE_PANEL_BORDER_RANGES))
    visible = (
        border >= STRONG_RUNE_PANEL_BORDER_RATIO or
        (blue >= MIN_RUNE_PANEL_BLUE_RATIO and border >= MIN_RUNE_PANEL_BORDER_RATIO)
    )
    return visible, {'blue': blue, 'border': border}


def _split_rune_slots(arrow_roi):
    _, width = arrow_roi.shape[:2]
    slot_width = width / 4
    overlap = slot_width * SLOT_OVERLAP_RATIO
    slots = []
    for i in range(4):
        left = max(0, round(i * slot_width - overlap))
        right = min(width, round((i + 1) * slot_width + overlap))
        slots.append(arrow_roi[:, left:right])
    return slots


def run_inference_for_single_image(model, image):
    """
    Performs an inference once.
    :param model:   The model object to use.
    :param image:   The input image.
    :return:        The model's predictions including bounding boxes and classes.
    """

    image = np.asarray(image)

    input_tensor = tf.convert_to_tensor(image)
    input_tensor = input_tensor[tf.newaxis,...]

    model_fn = model.signatures['serving_default']
    output_dict = model_fn(input_tensor)

    output_dict = {key: value.numpy() for key, value in output_dict.items()}
    num_detections = _read_num_detections(output_dict.pop('num_detections'))
    output_dict = {
        key: _read_detection_output(value, num_detections)
        for key, value in output_dict.items()
    }
    output_dict['num_detections'] = num_detections
    if 'detection_classes' in output_dict:
        output_dict['detection_classes'] = output_dict['detection_classes'].astype(np.int64)
    return output_dict


def _read_num_detections(value):
    """Returns num_detections from scalar or batched TensorFlow outputs."""

    arr = np.asarray(value)
    if arr.size == 0:
        return 0
    return int(arr.reshape(-1)[0])


def _read_detection_output(value, num_detections):
    """Normalizes batched TensorFlow detection outputs to one image."""

    arr = np.asarray(value)
    if arr.ndim >= 2 and arr.shape[0] == 1:
        arr = arr[0]
    if arr.ndim >= 1:
        arr = arr[:num_detections]
    return arr


def sort_by_confidence(model, image):
    """
    Runs a single inference on the image and returns the best four classifications.
    :param model:   The model object to use.
    :param image:   The input image.
    :return:        The model's top four predictions.
    """

    output_dict = run_inference_for_single_image(model, image)
    zipped = list(zip(output_dict['detection_scores'],
                      output_dict['detection_boxes'],
                      output_dict['detection_classes']))
    pruned = [t for t in zipped if t[0] > 0.3] #0.5
    pruned.sort(key=lambda x: x[0], reverse=True)
    result = pruned[:4]
    return result


def get_boxes(model, image):
    """
    Returns the bounding boxes of the top four classified arrows.
    :param model:   The model object to predict with.
    :param image:   The input image.
    :return:        Up to four bounding boxes.
    """

    output_dict = run_inference_for_single_image(model, image)
    zipped = list(zip(output_dict['detection_scores'],
                      output_dict['detection_boxes'],
                      output_dict['detection_classes']))
    pruned = [t for t in zipped if t[0] > 0.3] #0.5
    pruned.sort(key=lambda x: x[0], reverse=True)
    pruned = pruned[:4]
    boxes = [t[1:] for t in pruned]
    return boxes


def detect_rune_slots(model, image, debug_dir=None, debug_prefix=''):
    """
    Detects rune arrows by splitting the rune panel into four independent slots.
    :return:    A four-item list containing directions or None, None if the rune panel is absent.
    """

    _, arrow_roi = _extract_rune_arrow_roi(image, debug_dir=debug_dir, debug_prefix=debug_prefix)
    if arrow_roi is None:
        return None

    panel_visible, metrics = _rune_panel_visible(arrow_roi)
    _save_debug_text(
        debug_dir,
        'debug.txt',
        f"{debug_prefix}panel blue={metrics['blue']:.4f} "
        f"border={metrics['border']:.4f} visible={panel_visible}"
    )
    if not panel_visible:
        _save_debug_text(debug_dir, 'debug.txt', f'{debug_prefix}rune panel not visible')
        return None

    slots = _split_rune_slots(arrow_roi)
    classes = []
    for index, slot in enumerate(slots):
        slot_prefix = f'{debug_prefix}slot{index}_'
        _save_debug_image(debug_dir, f'{slot_prefix}00.png', slot)
        direction = _detect_slot_arrow(
            model,
            slot,
            debug_dir=debug_dir,
            debug_prefix=slot_prefix,
        )
        classes.append(direction)
    _save_debug_text(debug_dir, 'debug.txt', f'{debug_prefix}slot_classes: {classes}')
    return classes


def _detect_slot_arrow(model, slot, debug_dir=None, debug_prefix=''):
    best = None

    for profile_name, ranges in _slot_hsv_profiles():
        profile_prefix = f'{debug_prefix}{profile_name}_'
        candidate = _detect_slot_arrow_profile(
            model,
            slot,
            profile_name,
            ranges,
            debug_dir=debug_dir,
            debug_prefix=profile_prefix,
        )
        if candidate is None:
            continue
        if candidate[1] >= SLOT_EARLY_ACCEPT_SCORE:
            best = candidate
            break
        if best is None or candidate[1] > best[1]:
            best = candidate

    if best is None:
        _save_debug_text(debug_dir, 'debug.txt', f'{debug_prefix}class: None')
        return None

    direction, score, profile_name, source = best
    _save_debug_text(
        debug_dir,
        'debug.txt',
        f'{debug_prefix}class: {direction} score={score:.3f} '
        f'profile={profile_name} source={source}'
    )
    return direction


def _detect_slot_arrow_profile(model, slot, profile_name, ranges, debug_dir=None, debug_prefix=''):
    mask = _color_mask(slot, ranges)
    ratio = _mask_ratio(mask)
    _save_debug_text(debug_dir, 'debug.txt', f'{debug_prefix}mask ratio: {ratio:.4f}')
    if ratio < MIN_SLOT_MASK_RATIO:
        _save_debug_text(debug_dir, 'debug.txt', f'{debug_prefix}skipping sparse slot')
        return None

    max_ratio = MAX_BROAD_SLOT_MASK_RATIO if profile_name == 'broad' else MAX_SLOT_MASK_RATIO
    if ratio > max_ratio:
        _save_debug_text(debug_dir, 'debug.txt', f'{debug_prefix}skipping noisy slot')
        return None

    filtered = _mask_image(slot, mask)
    cannied = canny(filtered)
    _save_debug_image(debug_dir, f'{debug_prefix}01_filtered.png', filtered)
    _save_debug_image(debug_dir, f'{debug_prefix}02_cannied.png', cannied)

    preprocessed = _pad_for_model(cannied)
    _save_debug_image(debug_dir, f'{debug_prefix}03_preprocessed.png', preprocessed)
    candidate = _classify_preprocessed_arrow(model, preprocessed)
    if candidate is None:
        _save_debug_text(debug_dir, 'debug.txt', f'{debug_prefix}class: None')
        return None

    direction, score, source = candidate
    _save_debug_text(
        debug_dir,
        'debug.txt',
        f'{debug_prefix}class: {direction} score={score:.3f} source={source}'
    )
    return direction, score, profile_name, source


def _pad_for_model(image):
    height, width, channels = image.shape
    scale = min(MODEL_PAD_WIDTH / width, MODEL_PAD_HEIGHT / height, 1)
    if scale < 1:
        image = cv2.resize(
            image,
            (max(1, round(width * scale)), max(1, round(height * scale))),
            interpolation=cv2.INTER_AREA
        )
        height, width, channels = image.shape

    preprocessed = np.full((MODEL_PAD_HEIGHT, MODEL_PAD_WIDTH, channels), (0, 0, 0), dtype=np.uint8)
    x_offset = (MODEL_PAD_WIDTH - width) // 2
    y_offset = (MODEL_PAD_HEIGHT - height) // 2
    if x_offset >= 0 and y_offset >= 0:
        preprocessed[y_offset:y_offset+height, x_offset:x_offset+width] = image
    return preprocessed


def _classify_preprocessed_arrow(model, image):
    label_map = {1: 'up', 2: 'down', 3: 'left', 4: 'right'}
    converter = {'up': 'right', 'down': 'left'}
    candidates = []

    for score, _, class_id in sort_by_confidence(model, image):
        if class_id in label_map:
            candidates.append((label_map[class_id], float(score), 'direct'))

    rotated = cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)
    for score, _, class_id in sort_by_confidence(model, rotated):
        if class_id in [1, 2]:
            direction = converter[label_map[class_id]]
            candidates.append((direction, float(score), 'rotated'))

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[1], reverse=True)
    return candidates[0]


@utils.run_if_enabled
def merge_detection(model, image, debug_dir=None, debug_prefix=''):
    """
    Run two inferences: one on the upright image, and one on the image rotated 90 degrees.
    Only considers vertical arrows and merges the results of the two inferences together.
    (Vertical arrows in the rotated image are actually horizontal arrows).
    :param model:   The model object to use.
    :param image:   The input image.
    :return:        A list of four arrow directions.
    """

    classes = []
    
    _, cropped = _extract_rune_arrow_roi(image, debug_dir=debug_dir, debug_prefix=debug_prefix)
    if cropped is None:
        return classes

    for profile_name, ranges in _arrow_hsv_profiles():
        profile_prefix = f'{debug_prefix}{profile_name}_'
        classes = _merge_detection_profile(
            model,
            cropped,
            ranges,
            debug_dir=debug_dir,
            debug_prefix=profile_prefix,
        )
        _save_debug_text(debug_dir, 'debug.txt', f'{profile_prefix}classes: {classes}')
        if len(classes) == 4:
            return classes

    return classes


def _merge_detection_profile(model, cropped, ranges, debug_dir=None, debug_prefix=''):
    label_map = {1: 'up', 2: 'down', 3: 'left', 4: 'right'}
    converter = {'up': 'right', 'down': 'left'}         # For the 'rotated inferences'
    classes = []

    mask = _color_mask(cropped, ranges)
    ratio = _mask_ratio(mask)
    _save_debug_text(debug_dir, 'debug.txt', f'{debug_prefix}mask ratio: {ratio:.4f}')
    if ratio < MIN_ARROW_MASK_RATIO:
        _save_debug_text(debug_dir, 'debug.txt', f'{debug_prefix}skipping sparse frame')
        return classes
    if ratio > MAX_ARROW_MASK_RATIO:
        _save_debug_text(debug_dir, 'debug.txt', f'{debug_prefix}skipping noisy frame')
        return classes

    filtered = _mask_image(cropped, mask)
    cannied = canny(filtered)
    _save_debug_image(debug_dir, f'{debug_prefix}03_filtered.png', filtered)
    _save_debug_image(debug_dir, f'{debug_prefix}04_cannied.png', cannied)

    # Isolate the rune box
    height, width, channels = cannied.shape
    boxes = get_boxes(model, cannied)
    _save_debug_text(debug_dir, 'debug.txt', f'{debug_prefix}boxes found: {len(boxes)}')
    if len(boxes) == 4:      # Only run further inferences if arrows have been correctly detected
        y_mins = [b[0][0] for b in boxes]
        x_mins = [b[0][1] for b in boxes]
        y_maxes = [b[0][2] for b in boxes]
        x_maxes = [b[0][3] for b in boxes]
        left = int(round(min(x_mins) * width))
        right = int(round(max(x_maxes) * width))
        top = int(round(min(y_mins) * height))
        bottom = int(round(max(y_maxes) * height))
        rune_box = cannied[top:bottom, left:right]
        _save_debug_image(debug_dir, f'{debug_prefix}05_rune_box.png', rune_box)
        if rune_box.size == 0:
            _save_debug_text(debug_dir, 'debug.txt', f'{debug_prefix}rune_box is empty')
            return classes

        # Pad the rune box with black borders, effectively eliminating the noise around it
        height, width, channels = rune_box.shape
        scale = min(MODEL_PAD_WIDTH / width, MODEL_PAD_HEIGHT / height, 1)
        if scale < 1:
            rune_box = cv2.resize(
                rune_box,
                (max(1, round(width * scale)), max(1, round(height * scale))),
                interpolation=cv2.INTER_AREA
            )
            height, width, channels = rune_box.shape

        preprocessed = np.full((MODEL_PAD_HEIGHT, MODEL_PAD_WIDTH, channels), (0, 0, 0), dtype=np.uint8)
        x_offset = (MODEL_PAD_WIDTH - width) // 2
        y_offset = (MODEL_PAD_HEIGHT - height) // 2

        if x_offset >= 0 and y_offset >= 0:
            preprocessed[y_offset:y_offset+height, x_offset:x_offset+width] = rune_box
        _save_debug_image(debug_dir, f'{debug_prefix}06_preprocessed.png', preprocessed)

        # Run detection on preprocessed image
        lst = sort_by_confidence(model, preprocessed)
        lst.sort(key=lambda x: x[1][1])
        classes = [label_map[item[2]] for item in lst if item[2] in label_map]

        # Run detection on rotated image
        rotated = cv2.rotate(preprocessed, cv2.ROTATE_90_COUNTERCLOCKWISE)
        lst = sort_by_confidence(model, rotated)
        lst.sort(key=lambda x: x[1][2], reverse=True)
        rotated_classes = [converter[label_map[item[2]]]
                           for item in lst
                           if item[2] in [1, 2]]
            
        # Merge the two detection results
        for i in range(len(classes)):
            if rotated_classes and classes[i] in ['left', 'right']:
                classes[i] = rotated_classes.pop(0)

    return classes


def _save_debug_image(debug_dir, name, image):
    if not debug_dir:
        return
    os.makedirs(debug_dir, exist_ok=True)
    if image is not None and image.size > 0:
        cv2.imwrite(os.path.join(debug_dir, name), image)


def _save_debug_text(debug_dir, name, text):
    if not debug_dir:
        return
    os.makedirs(debug_dir, exist_ok=True)
    with open(os.path.join(debug_dir, name), 'a') as file:
        file.write(text + '\n')


# Script for testing the detection module by itself
if __name__ == '__main__':
    from src.common import config, utils
    import mss
    config.enabled = True
    monitor = {'top': 0, 'left': 0, 'width': 1366, 'height': 768}
    model = load_model()
    while True:
        with mss.mss() as sct:
            frame = np.array(sct.grab(monitor))
            cv2.imshow('frame', canny(filter_color(frame)))
            arrows = merge_detection(model, frame)
            print(arrows)
            if cv2.waitKey(1) & 0xFF == 27:     # 27 is ASCII for the Esc key
                break
