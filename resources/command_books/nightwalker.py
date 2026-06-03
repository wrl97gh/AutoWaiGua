"""A collection of all commands that Night Walker can use to interact with the game.

This file follows the same command-book style as shadower.py:
- Key maps MapleStory skills to keyboard keys.
- Each Command class exposes main(), which the routine engine can call.
- Tune key bindings and cooldown buckets to match your in-game hotkeys.
"""

from src.common import config, settings, utils
import time
import math
from src.routine.components import Command
from src.common.vkeys import press, key_down, key_up


# List of key mappings
class Key:
    # Movement
    JUMP = 'space'
    FLASH_JUMP = 'space'       # Night Walker's flash jump / Shadow Jump
    SHADOW_DODGE = '4'         # Optional; set to your Shadow Dodge / mobility key if you use it

    # Buffs
    DARK_SERVANT = '5'         # Shadow Partner-style clone
    MAPLE_WARRIOR = 'f1'
    GLORY_OF_GUARDIANS = 'f1'   # Cygnus hyper buff, NW equivalent of Epic Adventure
    SHADOW_BAT = '7'           # Optional toggle; be careful not to toggle it off accidentally

    # Decent / common buffs
    SPEED_INFUSION = None
    HOLY_SYMBOL = 'f4'
    SHARP_EYE = 'f3'
    COMBAT_ORDERS = 'f2'
    ADVANCED_BLESSING = None

    # Main skills
    QUINTUPLE_STAR = 'r'       # Main bossing / focused attack
    SHADOW_SPARK = 'q'         # Common mobbing attack if you use it
    DARK_OMEN = 'e'            # Bat summon / field attack
    SHADOW_BITE = 'w'          # 5th job map attack, key skill for bite farming
    SHADOW_SPEAR = '3'         # 5th job burst buff
    DOMINION = 'a'             # Hyper / burst skill
    RAPID_THROW = '1'          # 5th job burst, channeled
    GREATER_DARK_SERVANT = '2' # 5th job burst summon
    #SILENCE = 'f6'             # 6th job origin, optional; change/remove if unused

    # Common 5th job skills
    ARACHNID = 'f4'
    ERDA_SHOWER = 'f5'


#########################
#       Commands        #
#########################
def step(direction, target):
    """
    Performs one movement step in the given DIRECTION towards TARGET.
    Should not press any arrow keys, as those are handled by Auto Maple.
    """

    num_presses = 2
    if direction == 'up' or direction == 'down':
        num_presses = 1

    if config.stage_fright and direction != 'up' and utils.bernoulli(0.75):
        time.sleep(utils.rand_float(0.1, 0.3))

    d_y = target[1] - config.player_pos[1]
    if abs(d_y) > settings.move_tolerance * 1.5:
        if direction == 'down':
            press(Key.JUMP, 3)
        elif direction == 'up':
            press(Key.JUMP, 1)

    press(Key.FLASH_JUMP, num_presses)


def _face_direction_or_center(direction=None):
    """
    Faces the given horizontal direction. If direction is None, faces the center
    of the map based on normalized x position.
    """

    if direction:
        press(direction, 1, down_time=0.1, up_time=0.05)
    else:
        if config.player_pos[0] > 0.5:
            press('left', 1, down_time=0.1, up_time=0.05)
        else:
            press('right', 1, down_time=0.1, up_time=0.05)


class Adjust(Command):
    """Fine-tunes player position using small movements."""

    def __init__(self, x, y, max_steps=5):
        super().__init__(locals())
        self.target = (float(x), float(y))
        self.max_steps = settings.validate_nonnegative_int(max_steps)

    def main(self):
        counter = self.max_steps
        toggle = True
        error = utils.distance(config.player_pos, self.target)

        while config.enabled and counter > 0 and error > settings.adjust_tolerance:
            if toggle:
                d_x = self.target[0] - config.player_pos[0]
                threshold = settings.adjust_tolerance / math.sqrt(2)

                if abs(d_x) > threshold:
                    walk_counter = 0
                    if d_x < 0:
                        key_down('left')
                        while config.enabled and d_x < -1 * threshold and walk_counter < 60:
                            time.sleep(0.05)
                            walk_counter += 1
                            d_x = self.target[0] - config.player_pos[0]
                        key_up('left')
                    else:
                        key_down('right')
                        while config.enabled and d_x > threshold and walk_counter < 60:
                            time.sleep(0.05)
                            walk_counter += 1
                            d_x = self.target[0] - config.player_pos[0]
                        key_up('right')
                    counter -= 1
            else:
                d_y = self.target[1] - config.player_pos[1]
                if abs(d_y) > settings.adjust_tolerance / math.sqrt(2):
                    if d_y < 0:
                        FlashJump('up').main()
                    else:
                        key_down('down')
                        time.sleep(0.05)
                        press(Key.JUMP, 3, down_time=0.1)
                        key_up('down')
                        time.sleep(0.05)
                    counter -= 1

            error = utils.distance(config.player_pos, self.target)
            toggle = not toggle


class Buff(Command):
    """Uses Night Walker's recurring buffs once when their cooldown bucket is ready."""

    def __init__(self):
        super().__init__(locals())
        self.cd120_buff_time = 0
        self.cd180_buff_time = 0
        self.cd200_buff_time = 0
        self.cd900_buff_time = 0
        self.decent_buff_time = 0
        self.initial_toggle_time = 0

    def main(self):
        decent_buffs = [
            Key.SPEED_INFUSION,
            Key.HOLY_SYMBOL,
            Key.SHARP_EYE,
            Key.COMBAT_ORDERS,
            Key.ADVANCED_BLESSING,
        ]
        now = time.time()

        # Optional: press only once at script start.
        # If Shadow Bat/Ravenous Bat is already on, remove this block to avoid toggling it off.
        if self.initial_toggle_time == 0:
            press(Key.SHADOW_BAT, 2)
            self.initial_toggle_time = now

        if self.cd120_buff_time == 0 or now - self.cd120_buff_time > 120:
            press(Key.GLORY_OF_GUARDIANS, 2)
            self.cd120_buff_time = now

        # Put 180s burst buffs here if you want the farming script to auto-cast them.
        if self.cd180_buff_time == 0 or now - self.cd180_buff_time > 180:
            # These are useful, but may be too valuable to auto-use while bossing.
            # Uncomment if you want them in the automatic buff cycle.
            # press(Key.SHADOW_SPEAR, 2)
            # press(Key.GREATER_DARK_SERVANT, 2)
            # press(Key.DOMINION, 2)
            self.cd180_buff_time = now

        if self.cd200_buff_time == 0 or now - self.cd200_buff_time > 200:
            press(Key.DARK_SERVANT, 2)
            self.cd200_buff_time = now

        if self.cd900_buff_time == 0 or now - self.cd900_buff_time > 900:
            press(Key.MAPLE_WARRIOR, 2)
            self.cd900_buff_time = now

        if self.decent_buff_time == 0 or now - self.decent_buff_time > settings.buff_cooldown:
            for key in decent_buffs:
                if key:
                    press(key, 3, up_time=0.3)
            self.decent_buff_time = now


class FlashJump(Command):
    """Performs a flash jump in the given direction."""

    def __init__(self, direction):
        super().__init__(locals())
        self.direction = settings.validate_arrows(direction)

    def main(self):
        key_down(self.direction)
        time.sleep(0.1)
        press(Key.FLASH_JUMP, 1)
        press(Key.FLASH_JUMP, 1)
        key_up(self.direction)
        time.sleep(0.5)


class ShadowDodge(Command):
    """
    Uses Shadow Dodge / a bound mobility key in a direction, jumping if specified.
    If you do not use this skill, remove the class or bind Key.SHADOW_DODGE to another movement skill.
    """

    def __init__(self, direction, jump='False'):
        super().__init__(locals())
        self.direction = settings.validate_arrows(direction)
        self.jump = settings.validate_boolean(jump)

    def main(self):
        num_presses = 3
        time.sleep(0.05)

        if self.direction in ['up', 'down']:
            num_presses = 2

        if self.direction != 'up':
            key_down(self.direction)
            time.sleep(0.05)

        if self.jump:
            if self.direction == 'down':
                press(Key.JUMP, 3, down_time=0.1)
            else:
                press(Key.JUMP, 1)

        if self.direction == 'up':
            key_down(self.direction)
            time.sleep(0.05)

        press(Key.SHADOW_DODGE, num_presses)
        key_up(self.direction)

        if settings.record_layout:
            config.layout.add(*config.player_pos)


class QuintupleStar(Command):
    """Attacks using Quintuple Star in a horizontal direction."""

    def __init__(self, direction, attacks=2, repetitions=1):
        super().__init__(locals())
        self.direction = settings.validate_horizontal_arrows(direction)
        self.attacks = int(attacks)
        self.repetitions = int(repetitions)

    def main(self):
        time.sleep(0.05)
        key_down(self.direction)
        time.sleep(0.05)

        if config.stage_fright and utils.bernoulli(0.7):
            time.sleep(utils.rand_float(0.1, 0.3))

        for _ in range(self.repetitions):
            press(Key.QUINTUPLE_STAR, self.attacks, up_time=0.05)

        key_up(self.direction)

        if self.attacks > 2:
            time.sleep(0.3)
        else:
            time.sleep(0.2)


class QuintupleStarRandomDirection(Command):
    """Uses Quintuple Star once without forcing an arrow direction."""

    def main(self):
        press(Key.QUINTUPLE_STAR, 1, up_time=0.05)


class ShadowSpark(Command):
    """Attacks using Shadow Spark in a horizontal direction."""

    def __init__(self, direction, attacks=2, repetitions=1):
        super().__init__(locals())
        self.direction = settings.validate_horizontal_arrows(direction)
        self.attacks = int(attacks)
        self.repetitions = int(repetitions)

    def main(self):
        time.sleep(0.05)
        key_down(self.direction)
        time.sleep(0.05)

        if config.stage_fright and utils.bernoulli(0.7):
            time.sleep(utils.rand_float(0.1, 0.3))

        for _ in range(self.repetitions):
            press(Key.SHADOW_SPARK, self.attacks, up_time=0.05)

        key_up(self.direction)

        if self.attacks > 2:
            time.sleep(0.3)
        else:
            time.sleep(0.2)


class DarkOmen(Command):
    """
    Uses Dark Omen in a given direction, or towards the center of the map if
    no direction is specified.
    """

    def __init__(self, direction=None):
        super().__init__(locals())
        if direction is None:
            self.direction = direction
        else:
            self.direction = settings.validate_horizontal_arrows(direction)

    def main(self):
        _face_direction_or_center(self.direction)
        press(Key.DARK_OMEN, 3)


class ShadowBite(Command):
    """Uses Shadow Bite once."""

    def main(self):
        press(Key.SHADOW_BITE, 3)


class ShadowSpear(Command):
    """Uses Shadow Spear once."""

    def main(self):
        press(Key.SHADOW_SPEAR, 3)


class Dominion(Command):
    """Uses Dominion once."""

    def main(self):
        press(Key.DOMINION, 3)


class GreaterDarkServant(Command):
    """Uses Greater Dark Servant once."""

    def main(self):
        press(Key.GREATER_DARK_SERVANT, 3)


class RapidThrow(Command):
    """
    Uses Rapid Throw. This is a channeled burst skill, so channel_time controls
    how long the key is held.
    """

    def __init__(self, direction=None, channel_time=3.0):
        super().__init__(locals())
        if direction is None:
            self.direction = direction
        else:
            self.direction = settings.validate_horizontal_arrows(direction)
        self.channel_time = float(channel_time)

    def main(self):
        if self.direction:
            key_down(self.direction)
            time.sleep(0.05)

        key_down(Key.RAPID_THROW)
        time.sleep(self.channel_time)
        key_up(Key.RAPID_THROW)

        if self.direction:
            key_up(self.direction)

        time.sleep(0.2)


class Silence(Command):
    """Uses 6th job Origin skill Silence once. Remove this class if you have not unlocked it."""

    def main(self):
        press(Key.SILENCE, 3)


class ErdaShower(Command):
    """
    Use Erda Shower in a given direction, placing Erda Fountain if specified.
    Adds the player's position to the current Layout if necessary.
    """

    def __init__(self, direction, jump='False'):
        super().__init__(locals())
        self.direction = settings.validate_arrows(direction)
        self.jump = settings.validate_boolean(jump)

    def main(self):
        num_presses = 3
        time.sleep(0.05)

        if self.direction in ['up', 'down']:
            num_presses = 2

        if self.direction != 'up':
            key_down(self.direction)
            time.sleep(0.05)

        if self.jump:
            if self.direction == 'down':
                press(Key.JUMP, 3, down_time=0.1)
            else:
                press(Key.JUMP, 1)

        if self.direction == 'up':
            key_down(self.direction)
            time.sleep(0.05)

        press(Key.ERDA_SHOWER, num_presses)
        key_up(self.direction)

        if settings.record_layout:
            config.layout.add(*config.player_pos)


class Arachnid(Command):
    """Uses True Arachnid Reflection once."""

    def main(self):
        press(Key.ARACHNID, 3)


class NightWalkerBurst(Command):
    """
    A simple burst sequence for manual routine calls.
    Tune sleeps and order for your ping, animation locks, and whether you want
    to include Silence/Rapid Throw.
    """

    def __init__(self, direction=None, use_origin='False'):
        super().__init__(locals())
        if direction is None:
            self.direction = direction
        else:
            self.direction = settings.validate_horizontal_arrows(direction)
        self.use_origin = settings.validate_boolean(use_origin)

    def main(self):
        _face_direction_or_center(self.direction)
        press(Key.SHADOW_SPEAR, 3)
        time.sleep(0.3)

        press(Key.GREATER_DARK_SERVANT, 3)
        time.sleep(0.3)

        press(Key.DOMINION, 3)
        time.sleep(0.5)

        if self.use_origin:
            press(Key.SILENCE, 3)
            time.sleep(1.0)

        RapidThrow(self.direction, channel_time=3.0).main()
