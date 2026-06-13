"""Command-line entry point for the minimap Layout Builder."""

import argparse
import os
import sys
import time
import types


PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT)
os.chdir(PROJECT)

from src.common import config
from src.routine import layout_builder


def collect_live(duration):
    config.bot = types.SimpleNamespace(rune_active=False, rune_pos=(0, 0))
    from src.modules.capture import Capture

    capture = Capture()
    capture.start()
    print('Waiting for capture calibration...')
    while not capture.ready:
        time.sleep(0.1)
    print(
        f'Sampling for {duration:.0f}s. Move around and pause on '
        'different platforms.'
    )

    def progress(elapsed, total, samples):
        print(
            f'\rLive sampling: {elapsed:.0f}/{total:.0f}s, '
            f'{samples} standing samples',
            end='',
            flush=True
        )

    result = layout_builder.collect_live(
        capture, duration, progress=progress
    )
    print()
    return result


def main():
    parser = argparse.ArgumentParser(
        description='Build a Layout from minimap platforms.'
    )
    parser.add_argument(
        'name', help='layout name; must match the routine CSV base name'
    )
    parser.add_argument(
        '--frames', help='glob of saved full-frame screenshots of one map'
    )
    parser.add_argument(
        '--live', action='store_true', help='sample from the running game'
    )
    parser.add_argument('--duration', type=float, default=90)
    parser.add_argument(
        '--class',
        dest='class_name',
        default='nightwalker_leveling',
        help='command book name (layouts directory subfolder)'
    )
    parser.add_argument(
        '--out-dir', default=None, help='override the output directory'
    )
    parser.add_argument(
        '--dry-run', action='store_true', help='preview only, write nothing'
    )
    args = parser.parse_args()

    if bool(args.frames) == bool(args.live):
        parser.error('Use exactly one of --frames or --live')

    if args.frames:
        reference, samples = layout_builder.collect_offline(args.frames)
        print(f'Collected {len(samples)} player-position samples')
    else:
        reference, samples = collect_live(args.duration)

    result = layout_builder.build_layout(
        args.name,
        args.class_name,
        reference,
        samples,
        out_dir=args.out_dir,
        dry_run=args.dry_run
    )
    print(
        f"Extracted {result['platforms']} platforms from "
        f"{result['samples']} distinct standing positions."
    )
    print(f"Preview image: {result['preview_path']}")
    if result['saved']:
        print(
            f"Saved layout with {result['nodes']} nodes to "
            f"{result['out_path']}"
        )
    else:
        print(
            f"Dry run: would save {result['nodes']} nodes to "
            f"{result['out_path']}"
        )


if __name__ == '__main__':
    main()
