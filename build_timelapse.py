"""
build_timelapse.py — Combine GoPro time-lapse JPGs into an MP4 with hh:mm overlay.

Usage:  python build_timelapse.py
Output: snow_timelapse.mp4 in the same directory
"""

import os, glob, datetime
from PIL import Image, ImageDraw, ImageFont
from moviepy import ImageSequenceClip
import numpy as np

# ── Config ──────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
FOLDERS    = ["100GOPRO", "101GOPRO"]
OUTPUT     = os.path.join(BASE_DIR, "snow_timelapse.mp4")
FPS        = 30
FONT_PATH  = r"C:\Windows\Fonts\consola.ttf"
FONT_SIZE  = 80  # good visibility on 4K frames

# ── Gather and sort images by timestamp ─────────────────
print("Gathering images...")
files = []
for folder in FOLDERS:
    pattern = os.path.join(BASE_DIR, folder, "*.JPG")
    files.extend(glob.glob(pattern))

# Sort by last-modified time (the actual capture time)
files.sort(key=lambda f: os.path.getmtime(f))
print(f"Found {len(files)} images")

# ── Pre-load font ──────────────────────────────────────
font = ImageFont.truetype(FONT_PATH, FONT_SIZE)

# ── Build frames with timestamp overlay ────────────────
print("Building frames with timestamp overlay...")
frames = []
total = len(files)

for i, filepath in enumerate(files):
    img = Image.open(filepath)
    draw = ImageDraw.Draw(img)

    # Get capture time from file's last-modified timestamp
    mtime = os.path.getmtime(filepath)
    dt = datetime.datetime.fromtimestamp(mtime)
    label = dt.strftime("%H:%M")

    # Measure text and position in lower-right with padding
    bbox = draw.textbbox((0, 0), label, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    padding = 30
    x = img.width - tw - padding
    y = img.height - th - padding

    # Draw shadow then white text for readability
    draw.text((x + 3, y + 3), label, font=font, fill=(0, 0, 0))
    draw.text((x, y), label, font=font, fill=(255, 255, 255))

    frames.append(np.array(img))
    img.close()

    if (i + 1) % 100 == 0 or i == total - 1:
        print(f"  {i + 1}/{total}")

# ── Export video ───────────────────────────────────────
print(f"Encoding video at {FPS}fps...")
clip = ImageSequenceClip(frames, fps=FPS)
clip.write_videofile(OUTPUT, codec="libx264", threads=4, logger="bar")
clip.close()

print(f"\nDone! Output: {OUTPUT}")
print(f"Duration: {len(files)/FPS:.1f} seconds ({len(files)} frames @ {FPS}fps)")
