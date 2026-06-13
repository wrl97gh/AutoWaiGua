"""An interpreter that reads and executes user-created routines."""

import threading
import time
import os
from datetime import datetime
from src.common import config, settings, utils
from src.detection import detection, detection2, detection3
from src.detection.rune_dataset import RuneDatasetRecorder
from src.routine.routine import Routine
from src.command_book.command_book import CommandBook
from src.routine.components import Point
from src.common.vkeys import press
from src.common.interfaces import Configurable


RUNE_PANEL_WAIT_TIMEOUT = 0.8
RUNE_FAST_LEGACY_FRAMES = 2
RUNE_VOTE_FRAMES = 3
RUNE_LEGACY_FALLBACK_FRAMES = 1
RUNE_APPROACH_PORTAL_LOCK_SCALE = 0.2
RUNE_APPROACH_HORIZONTAL_OFFSET = 0.12

# Occasional human-like idle breaks: seconds between breaks and break length
BREAK_INTERVAL = (1200, 2700)
BREAK_DURATION = (8, 45)


class Bot(Configurable):
    """A class that interprets and executes user-defined routines."""

    DEFAULT_CONFIG = {
        'Interact': 'command',
        'Feed pet': '9'
    }

    def __init__(self):
        """Loads a user-defined routine on start up and initializes this Bot's main thread."""

        super().__init__('keybindings')
        config.bot = self

        self.rune_active = False
        self.rune_pos = (0, 0)
        self.rune_closest_pos = (0, 0)      # Location of the Point closest to rune
        self.submodules = []                # Always empty; the GUI Update menu iterates over it
        self.command_book = None            # CommandBook instance

        config.routine = Routine()

        self.ready = False
        self.thread = threading.Thread(target=self._main)
        self.thread.daemon = True

    def start(self):
        """
        Starts this Bot object's thread.
        :return:    None
        """

        print('\n[~] Started main bot loop')
        self.thread.start()

    def _main(self):
        """
        The main body of Bot that executes the user's routine.
        :return:    None
        """

        print('\n[~] Initializing detection algorithm:\n')
        try:
            model = detection.load_model()
            print('\n[~] Initialized detection algorithm')
        except FileNotFoundError as exc:
            model = None
            print(f'\n[!] {exc}')
            print('[!] Rune detection will be disabled until the model files are restored.')

        self.ready = True
        config.listener.enabled = True
        last_fed = time.time()
        next_break = time.time() + utils.rand_float(*BREAK_INTERVAL)
        while True:
            if config.enabled and len(config.routine) > 0:
                # Occasionally idle for a moment like a human stepping away
                if time.time() >= next_break and not self.rune_active:
                    duration = utils.rand_float(*BREAK_DURATION)
                    print(f'\n[~] Idling for {duration:.0f}s')
                    end = time.time() + duration
                    while config.enabled and time.time() < end:
                        time.sleep(0.5)
                    next_break = time.time() + utils.rand_float(*BREAK_INTERVAL)

                # Buff and feed pets
                self.command_book.buff.main()
                pet_settings = config.gui.settings.pets
                auto_feed = pet_settings.auto_feed.get()
                num_pets = pet_settings.num_pets.get()
                now = time.time()
                if auto_feed and now - last_fed > 1200 / num_pets * utils.rand_float(1.0, 1.12):
                    press(self.config['Feed pet'], 1)
                    last_fed = now

                # Highlight the current Point
                config.gui.view.routine.select(config.routine.index)
                config.gui.view.details.display_info(config.routine.index)

                # Execute next Point in the routine
                element = config.routine[config.routine.index]
                if model is not None and self.rune_active and isinstance(element, Point) \
                        and element.location == self.rune_closest_pos:
                    self._solve_rune(model)
                element.execute()
                config.routine.step()
            else:
                time.sleep(0.01)

    @utils.run_if_enabled
    def _solve_rune(self, model):
        """
        Moves to the position of the rune and solves the arrow-key puzzle.
        :param model:   The TensorFlow model to classify with.
        :param sct:     The mss instance object with which to take screenshots.
        :return:        None
        """

        # Shrink the portal UP-suppression zone during the approach so a portal
        # below the rune cannot block a required climb. Restored in finally.
        config.portal_lock_scale = 0.3
        try:
            approached = self._approach_and_interact_rune()
        finally:
            config.portal_lock_scale = 1.0
        if not approached:
            print('Could not get close enough to rune, retrying after the next rune detection')
            self.rune_active = False
            return

        print('\nSolving rune:')
        detection_engine = self._rune_detection_module()
        print(f'Rune detection engine: {self._rune_detection_name()}')
        debug_dir = None
        debug_enabled = self._rune_debug_enabled()
        if debug_enabled:
            debug_dir = os.path.abspath(os.path.join(
                'assets',
                'debug',
                'rune',
                datetime.now().strftime('%Y%m%d_%H%M%S')
            ))
        recorder = RuneDatasetRecorder(self._rune_detection_name()) if self._rune_dataset_enabled() else None
        last_frame_id = config.capture.frame_id
        frame, last_frame_id = self._wait_for_rune_panel(last_frame_id, debug_dir=debug_dir)
        print(f"Rune UI found: {'yes' if frame is not None else 'no'}")
        if recorder:
            recorder.add_frame(frame if frame is not None else config.capture.frame, 'panel')

        if detection_engine is detection2:
            # Fail-open: still attempt detection if the panel gate timed out,
            # so this path is never worse than running without the gate.
            solution, last_frame_id = self._legacy_rune_solution(
                detection_engine,
                model,
                last_frame_id,
                debug_dir,
                first_frame=frame,
                frames=5,
                prefix='detection2'
            )
            self._finalize_rune_attempt(solution, recorder, debug_dir)
            return

        if frame is None:
            self._finalize_rune_attempt(None, recorder, debug_dir)
            return
        solution, last_frame_id = self._legacy_rune_solution(
            detection_engine,
            model,
            last_frame_id,
            debug_dir,
            first_frame=frame,
            frames=RUNE_FAST_LEGACY_FRAMES,
            prefix='fast'
        )
        if solution is None:
            solution, last_frame_id = self._collect_rune_votes(
                detection_engine,
                model,
                None,
                last_frame_id,
                debug_dir
            )
        if solution is None:
            solution, last_frame_id = self._legacy_rune_solution(
                detection_engine,
                model,
                last_frame_id,
                debug_dir,
                frames=RUNE_LEGACY_FALLBACK_FRAMES,
                prefix='legacy'
            )

        self._finalize_rune_attempt(solution, recorder, debug_dir)

    def _finalize_rune_attempt(self, solution, recorder, debug_dir):
        """Enters SOLUTION if one was found, then records and reports the outcome."""

        post = None
        panel_gone = None
        if solution is not None:
            self._enter_rune_solution(solution)
            post = config.capture.frame
            if post is not None:
                panel_gone = not detection.find_rune_panel(post)
                print(f"Rune panel gone after entry: {'yes' if panel_gone else 'no'}")
        else:
            print('Could not solve rune, retrying after the next rune detection')
            if debug_dir:
                print(f'Rune debug images saved to: {debug_dir}')
            else:
                print('Rune debug image saving is disabled')

        if recorder:
            if post is not None:
                recorder.add_frame(post, 'after_entry')
            recorder.finish(solution, panel_gone)

        if config.remote is not None:
            if solution is not None:
                hint = ''
                if panel_gone is not None:
                    hint = ' (panel gone)' if panel_gone else ' (panel still visible!)'
                config.remote.notify(f"Rune: entered [{' '.join(solution)}]{hint}")
            else:
                config.remote.notify_frame('Rune solve failed, will retry on next detection')

        self.rune_active = False

    def _wait_for_rune_panel(self, last_frame_id, debug_dir=None, timeout=RUNE_PANEL_WAIT_TIMEOUT):
        start = time.time()
        last_frame = None
        while config.enabled and time.time() - start < timeout:
            frame, last_frame_id = self._wait_for_next_frame(last_frame_id, timeout=0.08)
            if frame is None:
                continue
            last_frame = frame
            if detection.find_rune_panel(frame):
                return frame, last_frame_id

        if debug_dir and last_frame is not None:
            detection.find_rune_panel(last_frame, debug_dir=debug_dir, debug_prefix='gate_')
        return None, last_frame_id

    def _collect_rune_votes(self, detection_engine, model, first_frame, last_frame_id, debug_dir):
        if not hasattr(detection_engine, 'detect_rune_slots'):
            return None, last_frame_id

        votes = [{} for _ in range(4)]
        min_votes = 2 if self._rune_confirmation_required() else 1
        frame = first_frame

        for i_ in range(RUNE_VOTE_FRAMES):
            if not config.enabled:
                return None, last_frame_id
            if frame is None:
                frame, last_frame_id = self._wait_for_next_frame(last_frame_id, timeout=0.35)
            if frame is None:
                continue

            slots = detection_engine.detect_rune_slots(
                model,
                frame,
                debug_dir=debug_dir,
                debug_prefix=f'{i_:02d}_'
            )
            if slots is None:
                print(f'Rune slots {i_:02d}: panel not visible')
                frame = None
                continue

            print(f'Rune slots {i_:02d}: {slots}')
            self._add_rune_votes(votes, slots)
            result = self._rune_vote_result(votes, min_votes)
            print(f'Rune vote {i_:02d}: {result if result else self._format_rune_votes(votes)}')
            if result:
                print(f'Rune vote result: {result}')
                return result, last_frame_id

            frame = None

        return None, last_frame_id

    def _legacy_rune_solution(self, detection_engine, model, last_frame_id, debug_dir, first_frame=None,
                              frames=RUNE_LEGACY_FALLBACK_FRAMES, prefix='legacy'):
        print(f'Trying {prefix} full-panel detection')
        inferences = set()
        confirm_twice = self._rune_confirmation_required()
        frame = first_frame
        for i_ in range(frames):
            if not config.enabled:
                return None, last_frame_id
            if frame is None:
                frame, last_frame_id = self._wait_for_next_frame(last_frame_id, timeout=0.25)
            if frame is None:
                continue
            solution = self._merge_rune_detection(
                detection_engine,
                model,
                frame,
                debug_dir=debug_dir,
                debug_prefix=f'{prefix}_{i_:02d}_'
            )
            print(f'Rune {prefix} inference {i_:02d}: {solution}')
            solution_key = tuple(solution)
            if len(solution) == 4 and (not confirm_twice or solution_key in inferences):
                print(f'Rune {prefix} result: {solution}')
                return solution, last_frame_id
            if len(solution) == 4:
                inferences.add(solution_key)
            frame = None

        return None, last_frame_id

    @staticmethod
    def _merge_rune_detection(detection_engine, model, frame, debug_dir=None, debug_prefix=''):
        if detection_engine is detection2:
            return detection_engine.merge_detection(model, frame) or []
        return detection_engine.merge_detection(
            model,
            frame,
            debug_dir=debug_dir,
            debug_prefix=debug_prefix
        ) or []

    @staticmethod
    def _add_rune_votes(votes, slots):
        for index, direction in enumerate(slots[:4]):
            if direction:
                votes[index][direction] = votes[index].get(direction, 0) + 1

    @staticmethod
    def _rune_vote_result(votes, min_votes):
        result = []
        for slot_votes in votes:
            if not slot_votes:
                return None
            ranked = sorted(slot_votes.items(), key=lambda item: item[1], reverse=True)
            direction, count = ranked[0]
            if count < min_votes:
                return None
            if len(ranked) > 1 and ranked[1][1] == count:
                return None
            result.append(direction)
        return result

    @staticmethod
    def _format_rune_votes(votes):
        result = []
        for slot_votes in votes:
            if not slot_votes:
                result.append('None')
                continue
            direction, count = max(slot_votes.items(), key=lambda item: item[1])
            result.append(f'{direction}:{count}')
        return '[' + ', '.join(result) + ']'

    @staticmethod
    def _rune_debug_enabled():
        try:
            return config.gui.settings.runes.save_debug.get()
        except Exception:
            return True

    @staticmethod
    def _rune_confirmation_required():
        try:
            return config.gui.settings.runes.confirm_twice.get()
        except Exception:
            return True

    @staticmethod
    def _rune_dataset_enabled():
        try:
            return config.gui.settings.runes.save_dataset.get()
        except Exception:
            return True

    @staticmethod
    def _rune_detection_name():
        try:
            return config.gui.settings.runes.detection_engine.get()
        except Exception:
            return 'detection1'

    @staticmethod
    def _rune_detection_module():
        name = Bot._rune_detection_name()
        if name == 'detection2':
            return detection2
        if name == 'detection3':
            return detection3
        return detection

    @staticmethod
    def _enter_rune_solution(solution):
        print('Solution found, entering result')
        # Brief reaction time before typing, like a player reading the rune
        time.sleep(utils.rand_float(0.2, 0.45))
        for i, arrow in enumerate(solution):
            press(arrow, 1, down_time=utils.rand_float(0.05, 0.09))
            if i < len(solution) - 1:
                time.sleep(utils.rand_float(0.08, 0.2))     # Uneven gap between keys
                if utils.bernoulli(0.1):                    # Occasional brief hesitation
                    time.sleep(utils.rand_float(0.12, 0.28))
        time.sleep(utils.rand_float(0.4, 0.7))
        print(f'Rune solved at: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')

    @staticmethod
    def _wait_for_next_frame(last_frame_id, timeout=1):
        start = time.time()
        while time.time() - start < timeout:
            current_frame_id = config.capture.frame_id
            if current_frame_id != last_frame_id:
                return config.capture.frame, current_frame_id
            time.sleep(0.01)
        return config.capture.frame, config.capture.frame_id

    def _approach_and_interact_rune(self, attempts=3):
        previous_portal_lock_scale = config.portal_lock_scale
        config.portal_lock_scale = RUNE_APPROACH_PORTAL_LOCK_SCALE
        try:
            move = self.command_book['move']
            adjust = self.command_book['adjust']
            flashjump = self.command_book['flashjump'] if 'flashjump' in self.command_book else None
            approach_sides = self._rune_approach_sides()

            for attempt in range(attempts):
                if self._interact_if_close_to_rune('Rune distance'):
                    return True

                side = approach_sides[attempt % len(approach_sides)]
                approach_target = self._rune_approach_target(side)
                print(f'Trying to approach rune from the {side}: '
                      f'({approach_target[0]:.3f}, {approach_target[1]:.3f})')
                move(*approach_target).execute()
                adjust(*approach_target).execute()

                move(*self.rune_pos).execute()
                adjust(*self.rune_pos).execute()

                if self._interact_if_close_to_rune('Rune distance after adjust'):
                    return True
                if self._catch_rune_interact_window('Rune distance after adjust settle'):
                    return True

                if flashjump is not None:
                    print('Trying upward flash jump to approach rune')
                    flashjump('up').execute()
                    adjust(*self.rune_pos).execute()
                    if self._interact_if_close_to_rune('Rune distance after upward flash jump'):
                        return True
                    if self._catch_rune_interact_window('Rune distance after upward flash jump settle'):
                        return True
                else:
                    print('No FlashJump command found in command book')

                time.sleep(0.1)

            return self._interact_if_close_to_rune('Rune distance')
        finally:
            config.portal_lock_scale = previous_portal_lock_scale

    def _rune_approach_sides(self):
        """Returns an edge-aware randomized order for approaching the rune."""

        offset = max(RUNE_APPROACH_HORIZONTAL_OFFSET, settings.move_tolerance * 1.25)
        rune_x = self.rune_pos[0]
        sides = []
        if rune_x - offset >= 0:
            sides.append('left')
        if rune_x + offset <= 1:
            sides.append('right')

        if not sides:
            sides.append('left' if rune_x >= 0.5 else 'right')
        elif len(sides) == 2 and utils.bernoulli(0.5):
            sides.reverse()
        return sides

    def _rune_approach_target(self, side):
        offset = max(RUNE_APPROACH_HORIZONTAL_OFFSET, settings.move_tolerance * 1.25)
        direction = -1 if side == 'left' else 1
        x = min(1.0, max(0.0, self.rune_pos[0] + direction * offset))
        return x, self.rune_pos[1]

    def _catch_rune_interact_window(self, label, duration=0.35, interval=0.02):
        deadline = time.time() + duration
        while time.time() < deadline:
            if self._interact_if_close_to_rune(label, log=False):
                return True
            time.sleep(interval)
        return False

    def _interact_if_close_to_rune(self, label, log=True):
        distance = utils.distance(config.player_pos, self.rune_pos)
        if log or distance <= settings.rune_interact_tolerance:
            print(f'{label}: {distance:.4f}')
        if distance <= settings.rune_interact_tolerance:
            press(self.config['Interact'], 1, down_time=0.2)
            return True
        return False

    def load_commands(self, file):
        try:
            self.command_book = CommandBook(file)
            config.gui.settings.update_class_bindings()
            if hasattr(config.gui.edit, 'resources'):
                config.gui.edit.resources.sync_selection()
            return True
        except ValueError:
            return False    # TODO: UI warning popup, say check cmd for errors
