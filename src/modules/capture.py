"""A module for tracking useful in-game information."""

import time
import cv2
import threading
import importlib
import mss
import numpy as np
from src.common import config, utils
from src.common import platform

platform.set_process_dpi_aware()


# The distance between the top of the minimap and the top of the screen
MINIMAP_TOP_BORDER = 5

# The thickness of the other three borders of the minimap
MINIMAP_BOTTOM_BORDER = 9

# Offset in pixels to adjust for windowed mode
WINDOWED_OFFSET_TOP = 36
WINDOWED_OFFSET_LEFT = 10

# Only search this portion of the screen when locating the minimap.
MINIMAP_SEARCH_WIDTH_RATIO = 0.5

# The top-left and bottom-right corners of the minimap
MM_TL_TEMPLATE = cv2.imread('assets/minimap_tl_template.png', 0)
MM_BR_TEMPLATE = cv2.imread('assets/minimap_br_template.png', 0)

MMT_HEIGHT = max(MM_TL_TEMPLATE.shape[0], MM_BR_TEMPLATE.shape[0])
MMT_WIDTH = max(MM_TL_TEMPLATE.shape[1], MM_BR_TEMPLATE.shape[1])

# The player's symbol on the minimap
PLAYER_TEMPLATE = cv2.imread('assets/player_template.png', 0)
PT_HEIGHT, PT_WIDTH = PLAYER_TEMPLATE.shape


class Capture:
    """
    A class that tracks player position and various in-game events. It constantly updates
    the config module with information regarding these events. It also annotates and
    displays the minimap in a pop-up window.
    """

    def __init__(self):
        """Initializes this Capture object's main thread."""

        config.capture = self

        self.frame = None
        self.frame_id = 0
        self.minimap = {}
        self.minimap_ratio = 1
        self.minimap_sample = None
        self.sct = None
        self.pixel_ratio = (1, 1)
        self.minimap_template_scale = (1, 1)
        self.window = {
            'left': 0,
            'top': 0,
            'width': 1366,
            'height': 768
        }

        self.ready = False
        self.calibrated = False
        self.thread = threading.Thread(target=self._main)
        self.thread.daemon = True

    def start(self):
        """Starts this Capture's thread."""

        print('\n[~] Started video capture')
        self.thread.start()

    def _main(self):
        """Constantly monitors the player's position and in-game events."""

        if platform.IS_WINDOWS:
            mss_windows = importlib.import_module('mss.windows')
            mss_windows.CAPTUREBLT = 0

        while True:
            # Calibrate screen capture
            rect = platform.find_window_rect('MapleStory')
            rect = tuple(max(0, x) for x in rect)

            self.window['left'] = rect[0]
            self.window['top'] = rect[1]
            self.window['width'] = max(rect[2] - rect[0], MMT_WIDTH)
            self.window['height'] = max(rect[3] - rect[1], MMT_HEIGHT)

            # Calibrate by finding the top-left and bottom-right corners of the minimap
            with mss.MSS() as self.sct:
                self.frame = self.screenshot()
            if self.frame is None:
                continue

            self.minimap_template_scale = (1, 1)
            search_width = max(MMT_WIDTH, round(self.frame.shape[1] * MINIMAP_SEARCH_WIDTH_RATIO))
            search_width = min(self.frame.shape[1], search_width)
            minimap_search_frame = self.frame[:, :search_width]
            tl, _ = utils.single_match(minimap_search_frame, MM_TL_TEMPLATE)
            _, br = utils.single_match(minimap_search_frame, MM_BR_TEMPLATE)
            mm_tl = (
                tl[0] + MINIMAP_BOTTOM_BORDER,
                tl[1] + MINIMAP_TOP_BORDER
            )
            mm_br = (
                max(mm_tl[0] + PT_WIDTH, br[0] - MINIMAP_BOTTOM_BORDER),
                max(mm_tl[1] + PT_HEIGHT, br[1] - MINIMAP_BOTTOM_BORDER)
            )
            self.minimap_ratio = (mm_br[0] - mm_tl[0]) / (mm_br[1] - mm_tl[1])
            self.minimap_sample = self.frame[mm_tl[1]:mm_br[1], mm_tl[0]:mm_br[0]]
            self.calibrated = True

            with mss.MSS() as self.sct:
                while True:
                    if not self.calibrated:
                        break

                    # Take screenshot
                    self.frame = self.screenshot()
                    if self.frame is None:
                        continue

                    # Crop the frame to only show the minimap
                    minimap = self.frame[mm_tl[1]:mm_br[1], mm_tl[0]:mm_br[0]]

                    # Determine the player's position
                    player = utils.multi_match(minimap, PLAYER_TEMPLATE, threshold=0.8)
                    if player:
                        config.player_pos = utils.convert_to_relative(player[0], minimap)

                    # Package display information to be polled by GUI
                    self.minimap = {
                        'minimap': minimap,
                        'rune_active': config.bot.rune_active,
                        'rune_pos': config.bot.rune_pos,
                        'path': config.path,
                        'player_pos': config.player_pos
                    }

                    if not self.ready:
                        self.ready = True
                    time.sleep(0.05)

    def screenshot(self, delay=1):
        try:
            frame = np.array(self.sct.grab(self.window))
            height, width = frame.shape[:2]
            self.pixel_ratio = (
                width / self.window['width'] if self.window['width'] else 1,
                height / self.window['height'] if self.window['height'] else 1
            )
            self.frame_id += 1
            return frame
        except mss.exception.ScreenShotError:
            print(f'\n[!] Error while taking screenshot, retrying in {delay} second'
                  + ('s' if delay != 1 else ''))
            time.sleep(delay)

    def frame_to_screen(self, point):
        """
        Converts a point from the current screenshot's pixel coordinates to the
        host OS screen coordinates used by mouse events.
        """

        ratio_x, ratio_y = self.pixel_ratio
        if ratio_x <= 0:
            ratio_x = 1
        if ratio_y <= 0:
            ratio_y = 1
        return (
            round(self.window['left'] + point[0] / ratio_x),
            round(self.window['top'] + point[1] / ratio_y)
        )

    def _scaled_px(self, value):
        scale = (self.pixel_ratio[0] + self.pixel_ratio[1]) / 2
        return max(1, round(value * scale))

    def _scaled_template(self, template):
        return self._resize_template(template, self.pixel_ratio)

    def scale_frame_template(self, template):
        """Scale a template that is matched against the full captured frame."""

        return self._resize_template(template, self.pixel_ratio)

    def scale_minimap_template(self, template):
        """Scale a template that is matched against the cropped minimap."""

        return self._resize_template(template, self.minimap_template_scale)

    @staticmethod
    def _resize_template(template, scale):
        ratio_x, ratio_y = scale
        if abs(ratio_x - 1) < 0.05 and abs(ratio_y - 1) < 0.05:
            return template

        width = max(1, round(template.shape[1] * ratio_x))
        height = max(1, round(template.shape[0] * ratio_y))
        interpolation = cv2.INTER_CUBIC if ratio_x > 1 or ratio_y > 1 else cv2.INTER_AREA
        return cv2.resize(template, (width, height), interpolation=interpolation)

    def _select_match_profile(self, frame):
        original = {
            'tl_template': MM_TL_TEMPLATE,
            'br_template': MM_BR_TEMPLATE,
            'player_template': PLAYER_TEMPLATE,
            'top_border': MINIMAP_TOP_BORDER,
            'bottom_border': MINIMAP_BOTTOM_BORDER,
            'template_scale': (1, 1),
        }

        scaled = {
            'tl_template': self._scaled_template(MM_TL_TEMPLATE),
            'br_template': self._scaled_template(MM_BR_TEMPLATE),
            'player_template': self._scaled_template(PLAYER_TEMPLATE),
            'top_border': self._scaled_px(MINIMAP_TOP_BORDER),
            'bottom_border': self._scaled_px(MINIMAP_BOTTOM_BORDER),
            'template_scale': self.pixel_ratio,
        }

        original_score = (
            self._single_match_score(frame, original['tl_template'])
            + self._single_match_score(frame, original['br_template'])
        )
        scaled_score = (
            self._single_match_score(frame, scaled['tl_template'])
            + self._single_match_score(frame, scaled['br_template'])
        )

        # Prefer the original templates unless scaling is clearly better. This
        # avoids breaking 1:1 captures where Retina correction is unnecessary.
        if scaled_score > original_score + 0.1:
            return scaled
        return original

    @staticmethod
    def _single_match(frame, template):
        _, top_left, bottom_right = Capture._single_match_info(frame, template)
        return top_left, bottom_right

    @staticmethod
    def _single_match_score(frame, template):
        score, _, _ = Capture._single_match_info(frame, template)
        return score

    @staticmethod
    def _single_match_info(frame, template):
        if template.shape[0] > frame.shape[0] or template.shape[1] > frame.shape[1]:
            return -1, (0, 0), (template.shape[1], template.shape[0])

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        result = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
        _, score, _, top_left = cv2.minMaxLoc(result)
        width, height = template.shape[::-1]
        bottom_right = (top_left[0] + width, top_left[1] + height)
        return score, top_left, bottom_right
