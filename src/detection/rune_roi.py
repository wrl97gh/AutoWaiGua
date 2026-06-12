"""
Rune-panel screen regions shared by the detection engines and offline tools.
Kept free of TensorFlow imports so labeling tools can start instantly.
"""

# The portion of the screen that contains the rune panel
RUNE_SCREEN_CROP = {
    'top': 120 / 768,
    'bottom': 0.5,
    'left': 0.25,
    'right': 0.75,
}

# The portion of the cropped region that contains the four arrows
RUNE_ARROW_ROI = {
    'top': 0.31,
    'bottom': 0.68,
    'left': 0.18,
    'right': 0.82,
}


def crop_screen_region(image):
    height, width = image.shape[:2]
    top = round(height * RUNE_SCREEN_CROP['top'])
    bottom = round(height * RUNE_SCREEN_CROP['bottom'])
    left = round(width * RUNE_SCREEN_CROP['left'])
    right = round(width * RUNE_SCREEN_CROP['right'])
    return image[top:bottom, left:right]


def crop_arrow_region(cropped):
    height, width = cropped.shape[:2]
    top = round(height * RUNE_ARROW_ROI['top'])
    bottom = round(height * RUNE_ARROW_ROI['bottom'])
    left = round(width * RUNE_ARROW_ROI['left'])
    right = round(width * RUNE_ARROW_ROI['right'])
    return cropped[top:bottom, left:right]


def extract_arrow_roi(frame):
    """Returns the four-arrow region cropped straight from a full frame."""

    return crop_arrow_region(crop_screen_region(frame))
