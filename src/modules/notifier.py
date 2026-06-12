"""A module for detecting and notifying the user of dangerous in-game events."""

from src.common import config, utils
import time
import os
import cv2
import pygame
import threading
import numpy as np
from datetime import datetime
from src.routine.components import Point
from src.common import controls


# A rune's symbol on the minimap
RUNE_RANGES = (
    ((135, 120, 240), (155, 180, 255)),
)
rune_filtered = utils.filter_color(cv2.imread('assets/rune_template.png'), RUNE_RANGES)
RUNE_TEMPLATE = cv2.cvtColor(rune_filtered, cv2.COLOR_BGR2GRAY)

# Other players' symbols on the minimap
OTHER_RANGES = (
    ((0, 245, 215), (10, 255, 255)),
)
other_filtered = utils.filter_color(cv2.imread('assets/other_template.png'), OTHER_RANGES)
OTHER_TEMPLATE = cv2.cvtColor(other_filtered, cv2.COLOR_BGR2GRAY)

# Portal symbols on the minimap (green concentric rings)
PORTAL_RANGES = (
    ((35, 120, 90), (75, 255, 255)),
)
portal_filtered = utils.filter_color(cv2.imread('assets/portal_template.png'), PORTAL_RANGES)
PORTAL_TEMPLATE = cv2.cvtColor(portal_filtered, cv2.COLOR_BGR2GRAY)
PORTAL_MEMORY_SECONDS = 120

# The control-break (struggle) QTE arrow buttons. Created from a screenshot
# with tools/make_struggle_templates.py; detection is disabled when missing.
# Both buttons are matched because monster effects often occlude one of them.
STRUGGLE_TEMPLATES = [
    template for template in (
        cv2.imread('assets/struggle_left_template.png', 0),
        cv2.imread('assets/struggle_right_template.png', 0),
    ) if template is not None
]
STRUGGLE_SCALES = (1.0, 0.5)        # Handles Retina (2x) screenshots vs 1x capture
STRUGGLE_THRESHOLD = 0.65           # Tolerates effects partially covering the buttons
STRUGGLE_REGION = (0.05, 0.05, 0.95, 0.95)  # Search area: left, top, right, bottom ratios
STRUGGLE_CHECK_INTERVAL = 6                 # Check every Nth notifier cycle (~0.3s)
STRUGGLE_TIMEOUT = 15
STRUGGLE_MIN_MASH = 5                       # Mash blindly this long before any freed-check
STRUGGLE_CONFIRM_DELAY = 0.35               # Let the button-press flash settle
STRUGGLE_CONFIRM_CHECKS = 4                 # Fresh frames that must all be UI-free
STRUGGLE_CONFIRM_SPACING = 0.12             # Gap between confirmation frames
STRUGGLE_CHECK_EVERY = 4                    # Mash cycles between freed-checks
STRUGGLE_PRECHECK_PAUSE = 0.12              # Settle pause before each freed-check
STRUGGLE_DEBUG_DIR = os.path.join('assets', 'debug', 'struggle')

STRUGGLE_VARIANTS = []
for _template in STRUGGLE_TEMPLATES:
    for _scale in STRUGGLE_SCALES:
        if _scale == 1.0:
            STRUGGLE_VARIANTS.append(_template)
        else:
            STRUGGLE_VARIANTS.append(cv2.resize(
                _template, None, fx=_scale, fy=_scale, interpolation=cv2.INTER_AREA))

# The Elite Boss's warning sign
# ELITE_TEMPLATE = cv2.imread('assets/elite_template.jpg', 0)


def get_alert_path(name):
    return os.path.join(Notifier.ALERTS_DIR, f'{name}.mp3')


class Notifier:
    ALERTS_DIR = os.path.join('assets', 'alerts')

    def __init__(self):
        """Initializes this Notifier object's main thread."""

        pygame.mixer.init()
        self.mixer = pygame.mixer.music

        self.ready = False
        self.thread = threading.Thread(target=self._main)
        self.thread.daemon = True

        self.room_change_threshold = 0.9
        self.rune_alert_delay = 270         # 4.5 minutes
        self._portal_memory = {}
        self._portal_token = None

    def start(self):
        """Starts this Notifier's thread."""

        state = 'on' if STRUGGLE_VARIANTS else 'off (assets/struggle_*_template.png missing)'
        print(f'\n[~] Started notifier (struggle detection: {state})')
        self.thread.start()

    def _main(self):
        self.ready = True
        prev_others = 0
        last_player_alert = 0
        struggle_counter = 0
        rune_start_time = time.time()
        while True:
            if config.enabled:
                frame = config.capture.frame
                minimap_info = config.capture.minimap
                if frame is None or not minimap_info or 'minimap' not in minimap_info:
                    time.sleep(0.05)
                    continue

                minimap = minimap_info['minimap']
                if minimap is None or minimap.size == 0:
                    time.sleep(0.05)
                    continue

                # Check for the control-break QTE and mash arrows to escape it
                if STRUGGLE_VARIANTS:
                    struggle_counter = (struggle_counter + 1) % STRUGGLE_CHECK_INTERVAL
                    if struggle_counter == 0 and self._find_struggle_ui(frame):
                        self._break_control(frame)
                        continue

                # Check for unexpected black screen, sampling every 8th pixel
                # since the dark-pixel ratio doesn't need full resolution
                sampled = np.ascontiguousarray(frame[::8, ::8])
                gray = cv2.cvtColor(sampled, cv2.COLOR_BGR2GRAY)
                if np.count_nonzero(gray < 15) / gray.size > self.room_change_threshold:
                    self._alert('siren', reason='Black screen detected')
                    continue

                # Check for elite warning
                # TODO: Re-enable after elite boss template matching is reliable.
                # elite_frame = frame[height // 4:3 * height // 4, width // 4:3 * width // 4]
                # elite_template = config.capture.scale_frame_template(ELITE_TEMPLATE)
                # elite = utils.multi_match(elite_frame, elite_template, threshold=0.9)
                # if len(elite) > 0:
                #     self._alert('siren')
                #     continue

                # Check for other players entering the map. While anyone else
                # is present, stage_fright makes movement/attacks hesitate.
                filtered = utils.filter_color(minimap, OTHER_RANGES)
                other_template = config.capture.scale_minimap_template(OTHER_TEMPLATE)
                others = len(utils.multi_match(filtered, other_template, threshold=0.5))
                config.stage_fright = others > 0
                if others != prev_others:
                    if others > prev_others:
                        self._ping('ding')
                        if config.remote is not None and time.time() - last_player_alert > 60:
                            last_player_alert = time.time()
                            config.remote.notify(f'Another player appeared on the map '
                                                 f'({others} total)')
                    prev_others = others

                # Track portal locations so movement can avoid entering them
                self._track_portals(minimap)
                if controls.is_held('up') and controls.near_portal():
                    controls.key_up('up')
                    print('[~] Released held UP near a portal')

                # Check for rune
                now = time.time()
                if not config.bot.rune_active:
                    filtered = utils.filter_color(minimap, RUNE_RANGES)
                    rune_template = config.capture.scale_minimap_template(RUNE_TEMPLATE)
                    #print( 'fliter', filtered.shape[0],filtered.shape[1])
    
                    #print( 'mathces', matches)
                    matches = utils.multi_match(filtered, rune_template, threshold=0.9)
                    #print( 'fliter', filtered)
                    #print( 'mathces', matches[0])
                    rune_start_time = now
                    if matches and config.routine.sequence:
                        abs_rune_pos = (matches[0][0], matches[0][1])
                        config.bot.rune_pos = utils.convert_to_relative(abs_rune_pos, minimap)
                        distances = list(map(distance_to_rune, config.routine.sequence))
                        finite_distances = [d for d in distances if np.isfinite(d)]
                        if finite_distances:
                            index = np.argmin(distances)
                            config.bot.rune_closest_pos = config.routine[index].location
                            config.bot.rune_active = True
                            self._ping('rune_appeared', volume=0.75)
                elif now - rune_start_time > self.rune_alert_delay:     # Alert if rune hasn't been solved
                    config.bot.rune_active = False
                    self._alert('siren', reason='Rune not solved within 4.5 minutes')
                    continue
            time.sleep(0.05)

    @staticmethod
    def _find_struggle_ui(frame):
        """Returns True when the control-break arrow buttons are on screen."""

        height, width = frame.shape[:2]
        crop = frame[round(height * STRUGGLE_REGION[1]):round(height * STRUGGLE_REGION[3]),
                     round(width * STRUGGLE_REGION[0]):round(width * STRUGGLE_REGION[2])]
        if crop.size == 0:
            return False
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        for template in STRUGGLE_VARIANTS:
            if template.shape[0] > gray.shape[0] or template.shape[1] > gray.shape[1]:
                continue
            result = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
            if cv2.minMaxLoc(result)[1] >= STRUGGLE_THRESHOLD:
                return True
        return False

    def _break_control(self, trigger_frame):
        """Mashes left/right until the struggle UI disappears or times out."""

        print('\n[!] Character is being controlled! Mashing left/right to break free')
        path = self._save_struggle_frame(trigger_frame)
        if path:
            print(f'Struggle screenshot saved to: {path}')
        if config.remote is not None:
            config.remote.notify_frame('Character is being controlled, trying to break free...',
                                       trigger_frame)

        start = time.time()
        presses = 0
        freed = False
        # Pause the bot thread's key output: held movement keys and skill
        # presses would otherwise corrupt the alternating left/right input.
        controls.pause_input()
        try:
            for key in ('left', 'right', 'up', 'down'):
                controls.key_up(key)        # Clear any keys the bot is holding
            time.sleep(0.1)
            cycle = 0
            while config.enabled and time.time() - start < STRUGGLE_TIMEOUT:
                # Fast human pace: ~15 presses/s with jitter and brief hesitation
                for key in ('left', 'right'):
                    controls.press(key, 1, down_time=0.033, up_time=0.035)
                presses += 2
                if utils.bernoulli(0.08):
                    time.sleep(utils.rand_float(0.06, 0.15))

                cycle += 1
                if time.time() - start < STRUGGLE_MIN_MASH:
                    continue        # Mash unconditionally before checking at all
                if cycle % STRUGGLE_CHECK_EVERY:
                    continue
                # Pause briefly so the button-press flash settles before checking
                time.sleep(STRUGGLE_PRECHECK_PAUSE)
                frame = config.capture.frame
                if frame is not None and not self._find_struggle_ui(frame) \
                        and self._confirm_struggle_over():
                    freed = True
                    break
        finally:
            controls.resume_input()

        if freed:
            duration = time.time() - start
            print(f'[~] Broke free after {duration:.1f}s ({presses} presses)')
            if config.remote is not None:
                config.remote.notify(f'Broke free from control after {duration:.1f}s '
                                     f'({presses} presses)')
        elif config.enabled:
            self._alert('siren', reason='Could not break free from control')

    def _track_portals(self, minimap):
        """
        Updates config.portal_positions. Detections are remembered for a while
        because the player's own minimap dot covers a portal icon while
        standing on it, which is exactly when suppression matters most.
        """

        if config.capture.minimap_sample is not self._portal_token:
            self._portal_token = config.capture.minimap_sample
            self._portal_memory.clear()

        filtered = utils.filter_color(minimap, PORTAL_RANGES)
        portal_template = config.capture.scale_minimap_template(PORTAL_TEMPLATE)
        matches = _dedupe_matches(utils.multi_match(filtered, portal_template, threshold=0.8))
        now = time.time()
        for match in matches:
            rel = utils.convert_to_relative(match, minimap)
            key = (round(rel[0] / 0.015), round(rel[1] / 0.015))
            self._portal_memory[key] = (now, rel)

        config.portal_positions = [
            pos for seen, pos in self._portal_memory.values()
            if now - seen <= PORTAL_MEMORY_SECONDS
        ]

    def _confirm_struggle_over(self):
        """
        Verifies the struggle UI is really gone. The arrow buttons flash while
        being pressed, which makes single-frame checks unreliable during our
        own mashing: stop pressing, let the animation settle, then require
        several consecutive fresh frames without the UI.
        """

        time.sleep(STRUGGLE_CONFIRM_DELAY)
        last_id = config.capture.frame_id
        for _ in range(STRUGGLE_CONFIRM_CHECKS):
            deadline = time.time() + 0.3
            while config.capture.frame_id == last_id and time.time() < deadline:
                time.sleep(0.02)
            last_id = config.capture.frame_id
            frame = config.capture.frame
            if frame is not None and self._find_struggle_ui(frame):
                return False        # Still controlled, resume mashing
            time.sleep(STRUGGLE_CONFIRM_SPACING)
        return True

    @staticmethod
    def _save_struggle_frame(frame):
        if frame is None:
            return None
        try:
            os.makedirs(STRUGGLE_DEBUG_DIR, exist_ok=True)
            base = os.path.join(STRUGGLE_DEBUG_DIR, datetime.now().strftime('%Y%m%d_%H%M%S'))
            path = f'{base}.png'
            counter = 1
            while os.path.exists(path):
                path = f'{base}_{counter}.png'
                counter += 1
            cv2.imwrite(path, frame)
            return path
        except Exception as e:
            print(f'[!] Failed to save struggle screenshot: {e}')
            return None

    def _alert(self, name, volume=0.75, reason=''):
        """
        Plays an alert to notify user of a dangerous event. Stops the alert
        once the key bound to 'Start/stop' is pressed or a remote /stop
        command acknowledges it.
        """

        if config.ignore_siren_alerts:
            return

        config.enabled = False
        config.listener.enabled = False
        if config.remote is not None and reason:
            config.remote.notify_frame(f'ALERT: {reason} - bot stopped. Send /stop to silence the siren.')
        config.alert_ack = False
        self.mixer.load(get_alert_path(name))
        self.mixer.set_volume(volume)
        self.mixer.play(-1)
        while not controls.is_pressed(config.listener.config['Start/stop']) and not config.alert_ack:
            time.sleep(0.1)
        config.alert_ack = False
        self.mixer.stop()
        time.sleep(2)
        config.listener.enabled = True

    def _ping(self, name, volume=0.5):
        """A quick notification for non-dangerous events."""

        self.mixer.load(get_alert_path(name))
        self.mixer.set_volume(volume)
        self.mixer.play()


#################################
#       Helper Functions        #
#################################
def _dedupe_matches(matches, min_dist=8):
    """Collapses template matches that overlap the same minimap icon."""

    kept = []
    for m in matches:
        if all(abs(m[0] - k[0]) + abs(m[1] - k[1]) >= min_dist for k in kept):
            kept.append(m)
    return kept


def distance_to_rune(point):
    """
    Calculates the distance from POINT to the rune.
    :param point:   The position to check.
    :return:        The distance from POINT to the rune, infinity if it is not a Point object.
    """

    if isinstance(point, Point):
        return utils.distance(config.bot.rune_pos, point.location)
    return float('inf')
