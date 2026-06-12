"""
Sends the exact left/right mash sequence used by the struggle breaker, so you
can verify that the game actually receives the input.

Usage:
    python3 tools/test_struggle_input.py [seconds]

Click on the MapleStory window during the countdown. While the mash runs, the
character should visibly shuffle left and right in small steps. If it doesn't
move at all, the synthetic input is not reaching the game.
"""

import os
import sys
import time

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT)
os.chdir(PROJECT)

from src.common import config, controls, utils


def main():
    duration = float(sys.argv[1]) if len(sys.argv) > 1 else 3.0
    config.enabled = True       # Key presses are gated on this flag

    print('Click on the MapleStory window now!')
    for i in range(5, 0, -1):
        print(f'  starting in {i}...')
        time.sleep(1)

    print(f'Mashing left/right for {duration:.0f}s (same code path as the struggle breaker)')
    start = time.time()
    presses = 0
    while time.time() - start < duration:
        for key in ('left', 'right'):
            controls.press(key, 1, down_time=0.045, up_time=0.05)
        presses += 2
        if utils.bernoulli(0.1):
            time.sleep(utils.rand_float(0.08, 0.2))

    elapsed = time.time() - start
    print(f'Done: {presses} presses in {elapsed:.1f}s ({presses / elapsed:.1f} per second)')
    print('Did the character shuffle left/right? If not, check macOS Accessibility '
          'permission for the app that launched this script.')


if __name__ == '__main__':
    main()
