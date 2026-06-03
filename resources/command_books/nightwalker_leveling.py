"""A collection of commands that Night Walker can use to interact with MapleStory.

This version is tuned for Night Walker training/leveling:
- Keeps the original command-book interface used by Auto Maple routines.
- Adds common Night Walker training skills, common V skills, and buff commands.
- Adds safe key handling so optional/unbound skills can be left as None.

Important:
- Match the keys in class Key to your in-game key bindings.
- Toggle skills such as Shadow Bat/Ravenous Bat are not auto-pressed by default,
  because pressing them while already enabled can turn them off.
"""

from src.common import config, settings, utils
import time
import math
from src.routine.components import Command
from src.common.vkeys import press, key_down, key_up


# =========================
#        Settings
# =========================
# Toggle skills are dangerous to auto-cast because pressing them again can turn them off.
AUTO_TOGGLE_BATS_ON_FIRST_BUFF = False

# For pure farming, this can be True. If you also use the same script for bossing,
# keep it False so long-cooldown burst skills are only cast when called manually.
AUTO_USE_LONG_COOLDOWNS_IN_BUFF = True

# If your 6th job skills are not unlocked/bound, leave these as False/None.
AUTO_USE_ORIGIN_IN_BURST = False


# List of key mappings.
# Use lower-case letters for normal keys: 'q', 'w', 'r', etc.
# Use 'f1', 'f2', etc. for function keys. Leave unbound skills as None.
class Key:
    # Movement
    JUMP = 'space'
    FLASH_JUMP = 'space'          # Night Walker Shadow Jump / flash jump
    SHADOW_DODGE = '4'            # Optional mobility key. Set None if not bound.

    # Night Walker toggles / self buffs
    SHADOW_BAT = '7'              # Toggle. Do not auto-cast unless you know it starts off.
    RAVENOUS_BAT = None           # Toggle/alternate bat mode if you use it separately.
    DARK_SERVANT = '5'            # Shadow Partner-style clone / servant buff.
    SPIRIT_PROJECTION = None      # Optional throwing-star buff if bound.
    HASTE = None                  # Optional if not on pet auto-buff.
    MAPLE_WARRIOR = 'f1'          # Call of Cygnus / Maple Warrior equivalent.
    CYGNUS_BLESSING = None        # Transcendent Cygnus's Blessing / Cygnus Blessing if bound.
    GLORY_OF_GUARDIANS = 'f1'     # Cygnus hyper buff. Change if not same as Maple Warrior.
    LAST_RESORT = None            # Thief 5th job burst buff. Optional for leveling.
    SHADOW_ILLUSION = None        # Hyper/burst buff if bound.

    # Decent / common buffs
    SPEED_INFUSION = None
    HOLY_SYMBOL = 'f4'
    SHARP_EYE = 'f3'
    COMBAT_ORDERS = 'f2'
    ADVANCED_BLESSING = None

    # Main Night Walker training / attack skills
    QUINTUPLE_STAR = 'r'          # Main star attack; usually bossing/focused target.
    SHADOW_SPARK = 'q'            # Common mobbing attack.
    DARK_OMEN = 'e'               # Field/summon attack, very useful in training.
    SHADOW_BITE = 'w'             # 5th job map attack / bite farming skill.
    SHADOW_STITCH = None          # Bind / utility. Optional.
    STYGIAN_COMMAND = None        # 6th job/enhanced attack if bound. Optional.

    # Night Walker 5th/6th job burst and strong cooldown skills
    SHADOW_SPEAR = '3'
    DOMINION = 'a'
    RAPID_THROW = '1'
    GREATER_DARK_SERVANT = '2'
    SILENCE = None                # 6th job Origin. Set to your key if unlocked/bound.

    # Common 5th/6th job map skills
    CYGNUS_PHALANX = None         # Also known as Phalanx Charge in some references.
    PHALANX_CHARGE = CYGNUS_PHALANX
    ERDA_SHOWER = 'f5'            # Erda Shower / Erda Fountain.
    ARACHNID = None               # True Arachnid Reflection / Spider in Mirror.
    SOLAR_CREST = None            # Crest of the Solar, if unlocked/bound.
    Soul_Skill = None #boss soul skill
    


#########################
#       Utilities       #
#########################
def _press_skill(key, presses=1, down_time=0.0, up_time=0.05):
    """Presses a key only if it is bound. Returns True if something was pressed."""

    if key is None:
        return False
    press(key, presses, down_time=down_time, up_time=up_time)
    return True


def _hold_skill(key, hold_time):
    """Holds a key only if it is bound. Returns True if something was held."""

    if key is None:
        return False
    key_down(key)
    time.sleep(float(hold_time))
    key_up(key)
    return True


def _key(name):
    """Reads a Key attribute at execution time so GUI keybinding edits take effect."""

    return getattr(Key, name, None)


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


def _ready(last_cast_time, cooldown, now=None):
    """Returns True if a cooldown bucket is ready."""

    now = time.time() if now is None else now
    return last_cast_time == 0 or now - last_cast_time > float(cooldown)


def step(direction, target):
    """
    Performs one movement step in the given DIRECTION towards TARGET.
    Should not press arrow keys directly, as those are handled by Auto Maple.
    """

    num_presses = 2
    if direction in ['up', 'down']:
        num_presses = 1

    if config.stage_fright and direction != 'up' and utils.bernoulli(0.75):
        time.sleep(utils.rand_float(0.1, 0.3))

    d_y = target[1] - config.player_pos[1]
    if abs(d_y) > settings.move_tolerance * 1.5:
        if direction == 'down':
            _press_skill(Key.JUMP, 3)
        elif direction == 'up':
            _press_skill(Key.JUMP, 1)

    _press_skill(Key.FLASH_JUMP, num_presses)


#########################
#       Commands        #
#########################
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
                        _press_skill(Key.JUMP, 3, down_time=0.1)
                        key_up('down')
                        time.sleep(0.05)
                    counter -= 1

            error = utils.distance(config.player_pos, self.target)
            toggle = not toggle


class Buff(Command):
    """
    Uses Night Walker's recurring training buffs when their cooldown buckets are ready.

    Default behavior is conservative:
    - Decent/common buffs are auto-cast.
    - Dark Servant and Maple Warrior are auto-cast.
    - Bat toggles are NOT auto-cast unless AUTO_TOGGLE_BATS_ON_FIRST_BUFF is True.
    - Long-cooldown burst skills are NOT auto-cast unless AUTO_USE_LONG_COOLDOWNS_IN_BUFF is True.
    """

    def __init__(self):
        super().__init__(locals())
        self.initial_toggle_time = 0
        self.cd120_buff_time = 0
        self.cd180_buff_time = 0
        self.cd200_buff_time = 0
        self.cd900_buff_time = 0
        self.decent_buff_time = 0

    def main(self):
        now = time.time()

        if AUTO_TOGGLE_BATS_ON_FIRST_BUFF and self.initial_toggle_time == 0:
            _press_skill(Key.SHADOW_BAT, 2, up_time=0.1)
            _press_skill(Key.RAVENOUS_BAT, 2, up_time=0.1)
            self.initial_toggle_time = now

        # Around 120s class/common buffs.
        if _ready(self.cd120_buff_time, 120, now):
            _press_skill(Key.GLORY_OF_GUARDIANS, 2, up_time=0.2)
            _press_skill(Key.CYGNUS_BLESSING, 2, up_time=0.2)
            self.cd120_buff_time = now

        # Long cooldowns. Useful for leveling rotations, but disabled by default.
        if AUTO_USE_LONG_COOLDOWNS_IN_BUFF and _ready(self.cd180_buff_time, 180, now):
            _press_skill(Key.LAST_RESORT, 2, up_time=0.2)
            _press_skill(Key.SHADOW_ILLUSION, 2, up_time=0.2)
            _press_skill(Key.SHADOW_SPEAR, 2, up_time=0.2)
            _press_skill(Key.GREATER_DARK_SERVANT, 2, up_time=0.2)
            _press_skill(Key.DOMINION, 2, up_time=0.2)
            self.cd180_buff_time = now

        # Long duration class buffs.
        if _ready(self.cd200_buff_time, 200, now):
            _press_skill(Key.DARK_SERVANT, 2, up_time=0.2)
            _press_skill(Key.HASTE, 2, up_time=0.2)
            _press_skill(Key.SPIRIT_PROJECTION, 2, up_time=0.2)
            self.cd200_buff_time = now

        if _ready(self.cd900_buff_time, 900, now):
            _press_skill(Key.MAPLE_WARRIOR, 2, up_time=0.2)
            self.cd900_buff_time = now

        if _ready(self.decent_buff_time, settings.buff_cooldown, now):
            for key in [
                Key.SPEED_INFUSION,
                Key.HOLY_SYMBOL,
                Key.SHARP_EYE,
                Key.COMBAT_ORDERS,
                Key.ADVANCED_BLESSING,
            ]:
                _press_skill(key, 3, up_time=0.3)
            self.decent_buff_time = now


class FlashJump(Command):
    """Performs a flash jump in the given direction."""

    def __init__(self, direction):
        super().__init__(locals())
        self.direction = settings.validate_arrows(direction)

    def main(self):
        key_down(self.direction)
        time.sleep(0.1)
        _press_skill(Key.JUMP, 1, down_time=0.08, up_time=0.08)
        _press_skill(Key.FLASH_JUMP, 1, down_time=0.08, up_time=0.08)
        key_up(self.direction)
        time.sleep(0.5)


class ShadowDodge(Command):
    """Uses Shadow Dodge / a bound mobility key in a direction, jumping if specified."""

    def __init__(self, direction, jump='False'):
        super().__init__(locals())
        self.direction = settings.validate_arrows(direction)
        self.jump = settings.validate_boolean(jump)

    def main(self):
        if Key.SHADOW_DODGE is None:
            return

        num_presses = 3
        time.sleep(0.05)

        if self.direction in ['up', 'down']:
            num_presses = 2

        if self.direction != 'up':
            key_down(self.direction)
            time.sleep(0.05)

        if self.jump:
            if self.direction == 'down':
                _press_skill(Key.JUMP, 3, down_time=0.1)
            else:
                _press_skill(Key.JUMP, 1)

        if self.direction == 'up':
            key_down(self.direction)
            time.sleep(0.05)

        _press_skill(Key.SHADOW_DODGE, num_presses)
        key_up(self.direction)

        if settings.record_layout:
            config.layout.add(*config.player_pos)


class _HorizontalAttack(Command):
    """Shared logic for horizontal spam attacks."""

    KEY_NAME = None

    def __init__(self, direction, attacks=2, repetitions=1):
        super().__init__(locals())
        self.direction = settings.validate_horizontal_arrows(direction)
        self.attacks = int(attacks)
        self.repetitions = int(repetitions)

    def main(self):
        key = _key(self.KEY_NAME)
        if key is None:
            return

        time.sleep(0.05)
        key_down(self.direction)
        time.sleep(0.05)

        if config.stage_fright and utils.bernoulli(0.7):
            time.sleep(utils.rand_float(0.1, 0.3))

        for _ in range(self.repetitions):
            _press_skill(key, self.attacks, up_time=0.05)

        key_up(self.direction)

        if self.attacks > 2:
            time.sleep(0.3)
        else:
            time.sleep(0.2)


class QuintupleStar(_HorizontalAttack):
    """Attacks using Quintuple Star in a horizontal direction."""

    KEY_NAME = 'QUINTUPLE_STAR'


class ShadowSpark(_HorizontalAttack):
    """Attacks using Shadow Spark in a horizontal direction. Main low-friction mobbing option."""

    KEY_NAME = 'SHADOW_SPARK'


class StygianCommand(_HorizontalAttack):
    """Uses Stygian Command / 6th job-enhanced attack in a horizontal direction if bound."""

    KEY_NAME = 'STYGIAN_COMMAND'


class QuintupleStarRandomDirection(Command):
    """Uses Quintuple Star once without forcing an arrow direction."""

    def main(self):
        _press_skill(Key.QUINTUPLE_STAR, 1, up_time=0.05)


class ShadowSparkRandomDirection(Command):
    """Uses Shadow Spark once without forcing an arrow direction."""

    def main(self):
        _press_skill(Key.SHADOW_SPARK, 1, up_time=0.05)


class DarkOmen(Command):
    """Uses Dark Omen in a given direction, or towards the center if omitted."""

    def main(self):
        _press_skill(Key.DARK_OMEN, 3)

class SoulSkill(Command):

    def main(self):
        _press_skill(Key.Soul_Skill, 3)

class ShadowBite(Command):
    """Uses Shadow Bite once."""

    def main(self):
        _press_skill(Key.SHADOW_BITE, 3)


class ShadowStitch(Command):
    """Uses Shadow Stitch once if bound."""

    def main(self):
        _press_skill(Key.SHADOW_STITCH, 3)


class ShadowSpear(Command):
    """Uses Shadow Spear once."""

    def main(self):
        _press_skill(Key.SHADOW_SPEAR, 3)


class Dominion(Command):
    """Uses Dominion once."""

    def main(self):
        _press_skill(Key.DOMINION, 3)


class GreaterDarkServant(Command):
    """Uses Greater Dark Servant once."""

    def main(self):
        _press_skill(Key.GREATER_DARK_SERVANT, 3)


class RapidThrow(Command):
    """Uses Rapid Throw. This is channeled, so channel_time controls how long the key is held."""

    def __init__(self, direction=None, channel_time=3.0):
        super().__init__(locals())
        if direction is None:
            self.direction = direction
        else:
            self.direction = settings.validate_horizontal_arrows(direction)
        self.channel_time = float(channel_time)

    def main(self):
        if Key.RAPID_THROW is None:
            return

        if self.direction:
            key_down(self.direction)
            time.sleep(0.05)

        _hold_skill(Key.RAPID_THROW, self.channel_time)

        if self.direction:
            key_up(self.direction)

        time.sleep(0.2)


class Silence(Command):
    """Uses 6th job Origin skill Silence once if unlocked/bound."""

    def main(self):
        _press_skill(Key.SILENCE, 3)


class ErdaShower(Command):
    """
    Uses Erda Shower/Fountain in a given direction. If jump=True, jumps first.
    Adds the player's position to the current Layout if recording is enabled.
    """

    def __init__(self, direction, jump='False'):
        super().__init__(locals())
        self.direction = settings.validate_arrows(direction)
        self.jump = settings.validate_boolean(jump)

    def main(self):
        if Key.ERDA_SHOWER is None:
            return

        num_presses = 3
        time.sleep(0.05)

        if self.direction in ['up', 'down']:
            num_presses = 2

        if self.direction != 'up':
            key_down(self.direction)
            time.sleep(0.05)

        if self.jump:
            if self.direction == 'down':
                _press_skill(Key.JUMP, 3, down_time=0.1)
            else:
                _press_skill(Key.JUMP, 1)

        if self.direction == 'up':
            key_down(self.direction)
            time.sleep(0.05)

        _press_skill(Key.ERDA_SHOWER, num_presses)
        key_up(self.direction)

        if settings.record_layout:
            config.layout.add(*config.player_pos)


class ErdaFountain(ErdaShower):
    """Alias for ErdaShower for routines that call the fountain name."""

    def main(self):
        _press_skill(Key.ERDA_SHOWER, 3)

class CygnusPhalanx(Command):
    """Uses Cygnus Phalanx / Phalanx Charge once if bound."""

    def __init__(self, direction=None):
        super().__init__(locals())
        if direction is None:
            self.direction = direction
        else:
            self.direction = settings.validate_horizontal_arrows(direction)

    def main(self):
        _face_direction_or_center(self.direction)
        _press_skill(Key.CYGNUS_PHALANX, 3)


class PhalanxCharge(CygnusPhalanx):
    """Alias for CygnusPhalanx."""

    pass


class Arachnid(Command):
    """Uses True Arachnid Reflection / Spider in Mirror once if bound."""

    def main(self):
        _press_skill(Key.ARACHNID, 3)


class SolarCrest(Command):
    """Uses Crest of the Solar once if bound."""

    def main(self):
        _press_skill(Key.SOLAR_CREST, 3)


# One-key commands for buffs/toggles, useful for manual routine calls.
class ShadowBat(Command):
    """Toggles Shadow Bat. Be careful: if already on, this can turn it off."""

    def main(self):
        _press_skill(Key.SHADOW_BAT, 2)


class RavenousBat(Command):
    """Toggles Ravenous Bat if bound. Be careful: if already on, this can turn it off."""

    def main(self):
        _press_skill(Key.RAVENOUS_BAT, 2)


class DarkServant(Command):
    """Uses Dark Servant once."""

    def main(self):
        _press_skill(Key.DARK_SERVANT, 2)


class SpiritProjection(Command):
    """Uses Spirit Projection once if bound."""

    def main(self):
        _press_skill(Key.SPIRIT_PROJECTION, 2)


class Haste(Command):
    """Uses Haste once if bound."""

    def main(self):
        _press_skill(Key.HASTE, 2)


class MapleWarrior(Command):
    """Uses Maple Warrior / Call of Cygnus once."""

    def main(self):
        _press_skill(Key.MAPLE_WARRIOR, 2)


class GloryOfGuardians(Command):
    """Uses Glory of the Guardians once."""

    def main(self):
        _press_skill(Key.GLORY_OF_GUARDIANS, 2)


class CygnusBlessing(Command):
    """Uses Transcendent Cygnus's Blessing / Cygnus Blessing if bound."""

    def main(self):
        _press_skill(Key.CYGNUS_BLESSING, 2)


class LastResort(Command):
    """Uses Last Resort once if bound."""

    def main(self):
        _press_skill(Key.LAST_RESORT, 2)


class ShadowIllusion(Command):
    """Uses Shadow Illusion once if bound."""

    def main(self):
        _press_skill(Key.SHADOW_ILLUSION, 2)


class LevelingRotation(Command):
    """
    Optional helper command for farming routes.

    Put this in a routine when you want the script to opportunistically cast
    common map-clearing skills with internal cooldown checks. It will skip any
    skill whose key is None.
    """

    def __init__(self, direction=None, use_long_cooldowns='False', use_common_summons='True'):
        super().__init__(locals())
        if direction is None:
            self.direction = direction
        else:
            self.direction = settings.validate_horizontal_arrows(direction)
        self.use_long_cooldowns = settings.validate_boolean(use_long_cooldowns)
        self.use_common_summons = settings.validate_boolean(use_common_summons)
        self.shadow_bite_time = 0
        self.dark_omen_time = 0
        self.cygnus_phalanx_time = 0
        self.erda_shower_time = 0
        self.arachnid_time = 0
        self.solar_crest_time = 0
        self.shadow_spear_time = 0
        self.dominion_time = 0
        self.greater_servant_time = 0

    def main(self):
        now = time.time()
        _face_direction_or_center(self.direction)

        # Short / medium cooldown training skills.
        if _ready(self.shadow_bite_time, 15, now):
            _press_skill(Key.SHADOW_BITE, 3)
            self.shadow_bite_time = now
            time.sleep(0.15)

        if _ready(self.dark_omen_time, 20, now):
            _press_skill(Key.DARK_OMEN, 3)
            self.dark_omen_time = now
            time.sleep(0.15)

        if self.use_common_summons and _ready(self.cygnus_phalanx_time, 30, now):
            _press_skill(Key.CYGNUS_PHALANX, 3)
            self.cygnus_phalanx_time = now
            time.sleep(0.15)

        if self.use_common_summons and _ready(self.erda_shower_time, 60, now):
            _press_skill(Key.ERDA_SHOWER, 3)
            self.erda_shower_time = now
            time.sleep(0.15)

        # Long cooldown map skills. Disabled unless use_long_cooldowns=True.
        if self.use_long_cooldowns:
            if _ready(self.shadow_spear_time, 120, now):
                _press_skill(Key.SHADOW_SPEAR, 3)
                self.shadow_spear_time = now
                time.sleep(0.2)

            if _ready(self.greater_servant_time, 120, now):
                _press_skill(Key.GREATER_DARK_SERVANT, 3)
                self.greater_servant_time = now
                time.sleep(0.2)

            if _ready(self.dominion_time, 180, now):
                _press_skill(Key.DOMINION, 3)
                self.dominion_time = now
                time.sleep(0.3)

            if _ready(self.arachnid_time, 250, now):
                _press_skill(Key.ARACHNID, 3)
                self.arachnid_time = now
                time.sleep(0.3)

            if _ready(self.solar_crest_time, 250, now):
                _press_skill(Key.SOLAR_CREST, 3)
                self.solar_crest_time = now
                time.sleep(0.3)


class NightWalkerBurst(Command):
    """
    A simple burst sequence for manual routine calls.
    The sequence skips any unbound key and can optionally include Silence.
    """

    def __init__(self, direction=None, use_origin='False'):
        super().__init__(locals())
        if direction is None:
            self.direction = direction
        else:
            self.direction = settings.validate_horizontal_arrows(direction)
        self.use_origin = settings.validate_boolean(use_origin) or AUTO_USE_ORIGIN_IN_BURST

    def main(self):
        _face_direction_or_center(self.direction)

        _press_skill(Key.CYGNUS_BLESSING, 2)
        time.sleep(0.15)
        _press_skill(Key.GLORY_OF_GUARDIANS, 2)
        time.sleep(0.15)
        _press_skill(Key.LAST_RESORT, 2)
        time.sleep(0.15)
        _press_skill(Key.SHADOW_ILLUSION, 2)
        time.sleep(0.15)
        _press_skill(Key.SHADOW_SPEAR, 3)
        time.sleep(0.3)
        _press_skill(Key.GREATER_DARK_SERVANT, 3)
        time.sleep(0.3)
        _press_skill(Key.DOMINION, 3)
        time.sleep(0.5)

        if self.use_origin:
            _press_skill(Key.SILENCE, 3)
            time.sleep(1.0)

        RapidThrow(self.direction, channel_time=3.0).main()
