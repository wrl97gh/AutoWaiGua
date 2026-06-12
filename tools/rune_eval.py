"""
Evaluates the rune detection engines against ground-truth labels created
with tools/rune_labeler.py.

Usage:
    python3 tools/rune_eval.py
    python3 tools/rune_eval.py --engines detection2,detection1
    python3 tools/rune_eval.py --cpu --max-frames 2

Reported metrics (frame level):
    exact        all four arrows correct
    wrong-entry  engine produced a full answer that is NOT correct
                 (this is what would have been typed into the game)
    no-answer    engine produced no usable answer
    slot-acc     per-arrow accuracy over answered slots
"""

import os
import sys
import time
import argparse
import statistics

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT)
os.chdir(PROJECT)


def main():
    parser = argparse.ArgumentParser(description='Evaluate rune engines against labels.')
    parser.add_argument('--engines', default='detection2,detection1,detection1-slots',
                        help='comma-separated: detection2, detection1, detection1-slots')
    parser.add_argument('--max-frames', type=int, default=3,
                        help='max panel frames evaluated per session')
    parser.add_argument('--cpu', action='store_true', help='disable the Metal GPU')
    parser.add_argument('--roots', nargs='+', default=None,
                        help='dataset directories to scan (default: '
                             'assets/rune_dataset and assets/debug/rune)')
    args = parser.parse_args()

    import tensorflow as tf
    if args.cpu:
        tf.config.set_visible_devices([], 'GPU')

    import cv2
    from src.common import config
    config.enabled = True
    from src.detection import detection, detection2, rune_dataset

    engines = {
        'detection2': lambda model, frame: detection2.merge_detection(model, frame) or [],
        'detection1': lambda model, frame: detection.merge_detection(model, frame) or [],
        'detection1-slots': lambda model, frame: detection.detect_rune_slots(model, frame) or [],
    }
    selected = [name.strip() for name in args.engines.split(',') if name.strip()]
    unknown = [name for name in selected if name not in engines]
    if unknown:
        print(f"Unknown engine(s): {', '.join(unknown)}. "
              f"Choose from: {', '.join(engines)}")
        return

    roots = args.roots or rune_dataset.DATASET_ROOTS
    sessions = [
        s for s in rune_dataset.list_sessions(roots)
        if s['label'] and s['label'].get('arrows')
    ]
    if not sessions:
        print('No labeled sessions found. Run tools/rune_labeler.py first.')
        return

    cases = []      # (session, frame path, truth)
    for sess in sessions:
        truth = sess['label']['arrows']
        for name in rune_dataset.panel_frames(sess['frames'])[:args.max_frames]:
            path = os.path.join(sess['directory'], name)
            cases.append((sess['name'], path, truth))
    print(f"Evaluating {len(selected)} engine(s) on {len(cases)} frames "
          f"from {len(sessions)} labeled sessions\n")

    model = detection.load_model()
    warm = cv2.imread(cases[0][1], cv2.IMREAD_UNCHANGED)
    for name in selected:
        engines[name](model, warm)

    print(f"{'engine':18s} {'frames':>6s} {'exact':>7s} {'wrong-entry':>11s} "
          f"{'no-answer':>9s} {'slot-acc':>8s} {'mean ms':>8s}")
    session_entries = {name: {} for name in selected}
    for name in selected:
        engine = engines[name]
        exact = wrong = no_answer = 0
        slot_total = slot_correct = 0
        times = []
        for sess_name, path, truth in cases:
            frame = cv2.imread(path, cv2.IMREAD_UNCHANGED)
            if frame is None:
                continue
            start = time.perf_counter()
            result = engine(model, frame)
            times.append(time.perf_counter() - start)

            answered = len(result) == 4 and all(result)
            if answered:
                if sess_name not in session_entries[name]:
                    session_entries[name][sess_name] = list(result) == truth
                if list(result) == truth:
                    exact += 1
                else:
                    wrong += 1
            else:
                no_answer += 1
            for predicted, actual in zip(result, truth):
                if predicted:
                    slot_total += 1
                    slot_correct += predicted == actual

        total = len(times)
        slot_acc = f'{slot_correct / slot_total:7.1%}' if slot_total else '    n/a'
        print(f'{name:18s} {total:6d} {exact / total:7.1%} {wrong / total:11.1%} '
              f'{no_answer / total:9.1%} {slot_acc:>8s} {statistics.mean(times) * 1000:8.1f}')

    print('\nSession level (first full answer per session = what the bot would enter):')
    print(f"{'engine':18s} {'entered':>8s} {'correct':>8s} {'wrong':>6s} {'silent':>7s}")
    for name in selected:
        entries = session_entries[name]
        correct = sum(1 for ok in entries.values() if ok)
        print(f'{name:18s} {len(entries):8d} {correct:8d} {len(entries) - correct:6d} '
              f'{len(sessions) - len(entries):7d}')


if __name__ == '__main__':
    main()
