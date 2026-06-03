"""A module for classifying directional arrows using TensorFlow."""

import cv2
import os
import tensorflow as tf
import numpy as np
from src.common import platform, utils

MODEL_DIR = 'assets/models/rune_model_rnn_filtered_cannied/saved_model'
REQUIRED_MODEL_FILES = (
    'saved_model.pb',
    os.path.join('variables', 'variables.index'),
    os.path.join('variables', 'variables.data-00000-of-00001'),
)
WINDOWS_ARROW_HSV_RANGES = (
    ((1, 100, 100), (75, 255, 255)),
)
MACOS_ARROW_HSV_RANGES = (
    # macOS screenshots shift rune arrows toward cyan/blue and dim some glow
    # pixels. This range was tuned against assets/debug/rune/20260601_153252.
    ((1, 60, 90), (125, 255, 255)),
)


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


def filter_color(image):
    """
    Filters out all colors not between orange and green on the HSV scale, which
    eliminates some noise around the arrows.
    :param image:   The input image.
    :return:        The color-filtered image.
    """

    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    ranges = WINDOWS_ARROW_HSV_RANGES if platform.IS_MACOS else WINDOWS_ARROW_HSV_RANGES
    mask = cv2.inRange(hsv, ranges[0][0], ranges[0][1])
    for lower, upper in ranges[1:]:
        mask = cv2.bitwise_or(mask, cv2.inRange(hsv, lower, upper))

    # Mask the image
    color_mask = mask > 0
    arrows = np.zeros_like(image, np.uint8)
    arrows[color_mask] = image[color_mask]
    return arrows


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
    pruned = [t for t in zipped if t[0] > 0] #0.5
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
    pruned = [t for t in zipped if t[0] > 0] #0.5
    pruned.sort(key=lambda x: x[0], reverse=True)
    pruned = pruned[:4]
    boxes = [t[1:] for t in pruned]
    return boxes


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

    label_map = {1: 'up', 2: 'down', 3: 'left', 4: 'right'}
    converter = {'up': 'right', 'down': 'left'}         # For the 'rotated inferences'
    classes = []
    
    # Preprocessing
    height, width, channels = image.shape
    crop_top = round(height * 120 / 768)
    cropped = image[crop_top:height//2, width//4:3*width//4]
    _save_debug_image(debug_dir, f'{debug_prefix}01_frame.png', image)
    _save_debug_image(debug_dir, f'{debug_prefix}02_cropped.png', cropped)
    if cropped.size == 0:
        _save_debug_text(debug_dir, 'debug.txt', f'{debug_prefix}cropped image is empty')
        return classes

    filtered = filter_color(cropped)
    cannied = canny(filtered)
    _save_debug_image(debug_dir, f'{debug_prefix}03_filtered.png', filtered)
    _save_debug_image(debug_dir, f'{debug_prefix}04_cannied.png', cannied)

    # Isolate the rune box
    height, width, channels = cannied.shape
    boxes = get_boxes(model, cannied)
    _save_debug_text(debug_dir, 'debug.txt', f'{debug_prefix}boxes found: {len(boxes)}\n{debug_prefix}classes: {classes}')
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
        pad_height, pad_width = 384, 455
        height, width, channels = rune_box.shape
        scale = min(pad_width / width, pad_height / height, 1)
        if scale < 1:
            rune_box = cv2.resize(
                rune_box,
                (max(1, round(width * scale)), max(1, round(height * scale))),
                interpolation=cv2.INTER_AREA
            )
            height, width, channels = rune_box.shape

        preprocessed = np.full((pad_height, pad_width, channels), (0, 0, 0), dtype=np.uint8)
        x_offset = (pad_width - width) // 2
        y_offset = (pad_height - height) // 2

        if x_offset >= 0 and y_offset >= 0:
            preprocessed[y_offset:y_offset+height, x_offset:x_offset+width] = rune_box
        _save_debug_image(debug_dir, f'{debug_prefix}06_preprocessed.png', preprocessed)

        # Run detection on preprocessed image
        lst = sort_by_confidence(model, preprocessed)
        lst.sort(key=lambda x: x[1][1])
        classes = [label_map[item[2]] for item in lst]

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
