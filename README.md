# Snow Time-Lapse Builder

A Python script that converts GoPro interval-capture photos into an editable MP4 video with a real-time clock overlay.

## What it does

This project was built to document a 22-hour snowstorm in South Plainfield, NJ (Feb 22-23, 2026). A GoPro captured one photo per minute across two memory card folders, producing 1,317 images. The script combines them into a single time-lapse video suitable for import into any video editor.

Each frame is stamped with the capture time (`hh:mm`) in the lower-right corner, drawn from the file's filesystem timestamp. The text uses white-on-black-shadow rendering for readability against any background.

## Output

- **Format:** MP4 (H.264) — universally compatible with Premiere, DaVinci Resolve, CapCut, etc.
- **Resolution:** Native GoPro resolution (4000x3000)
- **Frame rate:** 30fps — standard editing timeline rate, easy to slow down in post
- **Duration:** ~44 seconds for 1,317 frames

## Project structure

```
Snow-Feb-23/
  build_timelapse.py    # Main script
  pyproject.toml        # Project metadata and dependencies
  100GOPRO/             # First batch of GoPro JPGs (not in repo)
  101GOPRO/             # Second batch of GoPro JPGs (not in repo)
  snow_timelapse.mp4    # Output video (not in repo)
```

## Requirements

- Python 3.10+
- Dependencies listed in `pyproject.toml`:
  - **moviepy** — video encoding and clip assembly
  - **Pillow** — image loading and text overlay rendering
  - **numpy** — array handling for frame data

Install with:

```
pip install moviepy Pillow numpy
```

## Usage

1. Place your GoPro image folders (`100GOPRO/`, `101GOPRO/`) in the same directory as the script.
2. Run:

```
python build_timelapse.py
```

3. Output is written to `snow_timelapse.mp4` in the same directory.

## Configuration

Edit the constants at the top of `build_timelapse.py` to customize:

| Variable    | Default       | Description                              |
|-------------|---------------|------------------------------------------|
| `FOLDERS`   | `["100GOPRO", "101GOPRO"]` | GoPro image subdirectories  |
| `FPS`       | `30`          | Output frame rate                        |
| `FONT_PATH` | `consola.ttf` | Font for the timestamp overlay           |
| `FONT_SIZE` | `80`          | Font size in pixels (scaled for 4K)      |

## How it works

1. **Gather** — Scans the configured folders for `*.JPG` files.
2. **Sort** — Orders all images by filesystem last-modified time, which preserves the original capture sequence across folder boundaries.
3. **Overlay** — For each image, reads the file's modification timestamp, formats it as `hh:mm`, and draws it in the lower-right corner with a drop shadow for contrast.
4. **Encode** — Assembles all frames into an H.264 MP4 using moviepy with multi-threaded encoding.
