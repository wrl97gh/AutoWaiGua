"""An interpreter that reads and executes user-created routines."""

import threading
import time
import git
import cv2
import inspect
import importlib
import os
import traceback
from datetime import datetime
from tkinter import messagebox
from os.path import splitext, basename
from src.common import config, settings, utils
from src.detection import detection
from src.routine import components
from src.routine.routine import Routine
from src.command_book.command_book import CommandBook
from src.routine.components import Point
from src.common.vkeys import press, click
from src.common.interfaces import Configurable


# The rune's buff icon
RUNE_BUFF_TEMPLATE = cv2.imread('assets/rune_buff_template.jpg', 0)


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
        self.submodules = []
        self.command_book = None            # CommandBook instance
        # self.module_name = None
        # self.buff = components.Buff()

        # self.command_book = {}
        # for c in (components.Wait, components.Walk, components.Fall,
        #           components.Move, components.Adjust, components.Buff):
        #     self.command_book[c.__name__.lower()] = c

        config.routine = Routine()

        self.ready = False
        self.thread = threading.Thread(target=self._main)
        self.thread.daemon = True

    def start(self):
        """
        Starts this Bot object's thread.
        :return:    None
        """

        #self.update_submodules()
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
        while True:
            if config.enabled and len(config.routine) > 0:
                # Buff and feed pets
                self.command_book.buff.main()
                pet_settings = config.gui.settings.pets
                auto_feed = pet_settings.auto_feed.get()
                num_pets = pet_settings.num_pets.get()
                now = time.time()
                if auto_feed and now - last_fed > 1200 / num_pets:
                    press(self.config['Feed pet'], 1)
                    last_fed = now

                # Highlight the current Point
                config.gui.view.routine.select(config.routine.index)
                config.gui.view.details.display_info(config.routine.index)

                # Execute next Point in the routine
                element = config.routine[config.routine.index]
                print(element.location)
                #print(model is not None)
                print(self.rune_closest_pos)
                if model is not None and self.rune_active and isinstance(element, Point) \
                        and element.location == self.rune_closest_pos:
                    #print("xxxx")
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

        if not self._approach_rune():
            print('Could not get close enough to rune, retrying after the next rune detection')
            self.rune_active = False
            return

        time.sleep(0.2)
        press(self.config['Interact'], 1, down_time=0.2)        # Inherited from Configurable

        print('\nSolving rune:')
        inferences = []
        solved = False
        debug_dir = os.path.abspath(os.path.join(
            'assets',
            'debug',
            'rune',
            datetime.now().strftime('%Y%m%d_%H%M%S')
        ))
        last_frame_id = config.capture.frame_id
        for i_ in range(30):
            frame, last_frame_id = self._wait_for_next_frame(last_frame_id)
            if frame is None:
                continue
            solution = detection.merge_detection(
                model,
                frame,
                debug_dir=debug_dir,
                debug_prefix=f'{i_:02d}_'
            )
            print(i_, solution)
            if solution:
                print(', '.join(solution))
                if solution in inferences:
                    print('Solution found, entering result')
                    for arrow in solution:
                        press(arrow, 1, down_time=0.1)
                    time.sleep(1)
                    for _ in range(3):
                        time.sleep(0.3)
                        frame = config.capture.frame
                        rune_buff = utils.multi_match(frame[:frame.shape[0] // 8, :],
                                                      RUNE_BUFF_TEMPLATE,
                                                      threshold=0.9)
                        if rune_buff:
                            rune_buff_pos = min(rune_buff, key=lambda p: p[0])
                            target = config.capture.frame_to_screen(rune_buff_pos)
                            click(target, button='right')
                    self.rune_active = False
                    solved = True
                    break
                elif len(solution) == 4:
                    inferences.append(solution)
        if not solved:
            print('Could not solve rune, retrying after the next rune detection')
            print(f'Rune debug images saved to: {debug_dir}')
            self._show_rune_debug_popup(debug_dir)
            self.rune_active = False

    @staticmethod
    def _show_rune_debug_popup(debug_dir):
        def show():
            messagebox.showinfo(
                title='Rune detection failed',
                message='Rune detection failed. Debug images were saved to:\n\n' + debug_dir
            )

        try:
            config.gui.root.after(0, show)
        except Exception:
            pass

    @staticmethod
    def _wait_for_next_frame(last_frame_id, timeout=1):
        start = time.time()
        while time.time() - start < timeout:
            current_frame_id = config.capture.frame_id
            if current_frame_id != last_frame_id:
                return config.capture.frame, current_frame_id
            time.sleep(0.01)
        return config.capture.frame, config.capture.frame_id

    def _approach_rune(self, attempts=3):
        move = self.command_book['move']
        adjust = self.command_book['adjust']
        flashjump = self.command_book['flashjump'] if 'flashjump' in self.command_book else None

        for _ in range(attempts):
            distance = utils.distance(config.player_pos, self.rune_pos)
            print(f'Rune distance: {distance:.4f}')
            if distance <= settings.rune_interact_tolerance:
                return True

            move(*self.rune_pos).execute()
            adjust(*self.rune_pos).execute()

            distance = utils.distance(config.player_pos, self.rune_pos)
            print(f'Rune distance after adjust: {distance:.4f}')
            if distance <= settings.rune_interact_tolerance:
                return True

            if flashjump is not None:
                print('Trying upward flash jump to approach rune')
                flashjump('up').execute()
                adjust(*self.rune_pos).execute()
                distance = utils.distance(config.player_pos, self.rune_pos)
                print(f'Rune distance after upward flash jump: {distance:.4f}')
                if distance <= settings.rune_interact_tolerance:
                    return True
            else:
                print('No FlashJump command found in command book')

            time.sleep(0.1)

        distance = utils.distance(config.player_pos, self.rune_pos)
        print(f'Rune distance: {distance:.4f}')
        return distance <= settings.rune_interact_tolerance

    def load_commands(self, file):
        try:
            self.command_book = CommandBook(file)
            config.gui.settings.update_class_bindings()
        except ValueError:
            pass    # TODO: UI warning popup, say check cmd for errors
        #
        # utils.print_separator()
        # print(f"[~] Loading command book '{basename(file)}':")
        #
        # ext = splitext(file)[1]
        # if ext != '.py':
        #     print(f" !  '{ext}' is not a supported file extension.")
        #     return False
        #
        # new_step = components.step
        # new_cb = {}
        # for c in (components.Wait, components.Walk, components.Fall):
        #     new_cb[c.__name__.lower()] = c
        #
        # # Import the desired command book file
        # module_name = splitext(basename(file))[0]
        # target = '.'.join(['resources', 'command_books', module_name])
        # try:
        #     module = importlib.import_module(target)
        #     module = importlib.reload(module)
        # except ImportError:     # Display errors in the target Command Book
        #     print(' !  Errors during compilation:\n')
        #     for line in traceback.format_exc().split('\n'):
        #         line = line.rstrip()
        #         if line:
        #             print(' ' * 4 + line)
        #     print(f"\n !  Command book '{module_name}' was not loaded")
        #     return
        #
        # # Check if the 'step' function has been implemented
        # step_found = False
        # for name, func in inspect.getmembers(module, inspect.isfunction):
        #     if name.lower() == 'step':
        #         step_found = True
        #         new_step = func
        #
        # # Populate the new command book
        # for name, command in inspect.getmembers(module, inspect.isclass):
        #     new_cb[name.lower()] = command
        #
        # # Check if required commands have been implemented and overridden
        # required_found = True
        # for command in [components.Buff]:
        #     name = command.__name__.lower()
        #     if name not in new_cb:
        #         required_found = False
        #         new_cb[name] = command
        #         print(f" !  Error: Must implement required command '{name}'.")
        #
        # # Look for overridden movement commands
        # movement_found = True
        # for command in (components.Move, components.Adjust):
        #     name = command.__name__.lower()
        #     if name not in new_cb:
        #         movement_found = False
        #         new_cb[name] = command
        #
        # if not step_found and not movement_found:
        #     print(f" !  Error: Must either implement both 'Move' and 'Adjust' commands, "
        #           f"or the function 'step'")
        # if required_found and (step_found or movement_found):
        #     self.module_name = module_name
        #     self.command_book = new_cb
        #     self.buff = new_cb['buff']()
        #     components.step = new_step
        #     config.gui.menu.file.enable_routine_state()
        #     config.gui.view.status.set_cb(basename(file))
        #     config.routine.clear()
        #     print(f" ~  Successfully loaded command book '{module_name}'")
        # else:
        #     print(f" !  Command book '{module_name}' was not loaded")

    def update_submodules(self, force=False):
        """
        Pulls updates from the submodule repositories. If FORCE is True,
        rebuilds submodules by overwriting all local changes.
        """

        utils.print_separator()
        print('[~] Retrieving latest submodules:')
        self.submodules = []
        repo = git.Repo.init()
        with open('.gitmodules', 'r') as file:
            lines = file.readlines()
            i = 0
            while i < len(lines):
                if lines[i].startswith('[') and i < len(lines) - 2:
                    path = lines[i + 1].split('=')[1].strip()
                    url = lines[i + 2].split('=')[1].strip()
                    self.submodules.append(path)
