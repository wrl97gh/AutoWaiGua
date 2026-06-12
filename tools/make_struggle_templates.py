"""
Crops the control-break (struggle) arrow buttons out of a screenshot and saves
them as detection templates.

Usage:
    python3 tools/make_struggle_templates.py "<screenshot.png>"
    python3 tools/make_struggle_templates.py "<screenshot.png>" --box 170,80,50,50

Finds the two blue arrow buttons automatically via color segmentation. If that
fails, pass one button's region manually with --box x,y,w,h.
"""

import os
import sys
import argparse

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT)
os.chdir(PROJECT)

import cv2
import numpy as np

OUT_LEFT = os.path.join('assets', 'struggle_left_template.png')
OUT_RIGHT = os.path.join('assets', 'struggle_right_template.png')
BLUE_RANGE = ((100, 100, 150), (125, 255, 255))
BUTTON_EXPAND = 1.9     # Arrow glyph bbox -> full button sprite


def find_arrow_boxes(image):
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, BLUE_RANGE[0], BLUE_RANGE[1])
    mask = cv2.dilate(mask, np.ones((5, 5), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    candidates = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if 12 <= w <= 90 and 12 <= h <= 90 and 0.5 <= w / h <= 2.0:
            candidates.append((x, y, w, h))
    if len(candidates) < 2:
        return None

    # The two arrow glyphs are similar in size and vertically aligned
    candidates.sort(key=lambda b: b[2] * b[3], reverse=True)
    for i in range(len(candidates)):
        for j in range(i + 1, len(candidates)):
            a, b = candidates[i], candidates[j]
            if abs(a[1] - b[1]) < a[3] and 0.7 <= (a[2] * a[3]) / (b[2] * b[3]) <= 1.4:
                pair = sorted([a, b], key=lambda box: box[0])
                return pair
    return None


def expand_box(box, image_shape, factor=BUTTON_EXPAND):
    x, y, w, h = box
    size = round(max(w, h) * factor)
    cx, cy = x + w // 2, y + h // 2
    left = max(0, cx - size // 2)
    top = max(0, cy - size // 2)
    right = min(image_shape[1], left + size)
    bottom = min(image_shape[0], top + size)
    return left, top, right, bottom


def main():
    parser = argparse.ArgumentParser(description='Create struggle-UI templates from a screenshot.')
    parser.add_argument('screenshot', help='path to a screenshot showing the two arrow buttons')
    parser.add_argument('--box', help='manual fallback: one button as x,y,w,h')
    parser.add_argument('--expand', type=float, default=BUTTON_EXPAND,
                        help='arrow bbox expansion: ~1.9 = full button with bevel, '
                             '~1.3 = inner flat square and arrow only')
    args = parser.parse_args()

    image = cv2.imread(args.screenshot)
    if image is None:
        print(f'Could not read {args.screenshot}')
        return

    if args.box:
        x, y, w, h = (int(v) for v in args.box.split(','))
        boxes = [(x, y, w, h)]
        crops = [image[y:y + h, x:x + w]]
        outs = [OUT_LEFT]
    else:
        pair = find_arrow_boxes(image)
        if pair is None:
            print('Could not find the two arrow buttons automatically. '
                  'Re-run with --box x,y,w,h for one button.')
            return
        boxes = []
        crops = []
        for box in pair:
            left, top, right, bottom = expand_box(box, image.shape, factor=args.expand)
            boxes.append((left, top, right - left, bottom - top))
            crops.append(image[top:bottom, left:right])
        outs = [OUT_LEFT, OUT_RIGHT]

    for out, box, crop in zip(outs, boxes, crops):
        cv2.imwrite(out, crop)
        print(f'Saved {out}  (from x={box[0]} y={box[1]} {box[2]}x{box[3]})')

    preview = image.copy()
    for x, y, w, h in boxes:
        cv2.rectangle(preview, (x, y), (x + w, y + h), (0, 255, 0), 2)
    cv2.imwrite(os.path.join('assets', 'struggle_template_preview.png'), preview)
    print('Saved assets/struggle_template_preview.png (verify the green boxes)')


if __name__ == '__main__':
    main()
