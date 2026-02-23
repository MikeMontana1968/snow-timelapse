# Snow Time-Lapse Builder

A Python script that converts GoPro interval-capture photos into an editable MP4 video with a real-time clock overlay. Features an interactive CLI for folder selection, output naming, and frame rate configuration.

## What it does

This project was built to document a 22-hour snowstorm in South Plainfield, NJ (Feb 22-23, 2026). A GoPro captured one photo per minute across two memory card folders, producing 1,317 images. The script combines them into a single time-lapse video suitable for import into any video editor.

Each frame is stamped with the capture time (`hh:mm`) in the lower-right corner, drawn from the file's filesystem timestamp. The text uses white-on-black-shadow rendering for readability against any background.

## Output

- **Format:** MP4 (H.264) — universally compatible with Premiere, DaVinci Resolve, CapCut, etc.
- **Resolution:** Native GoPro resolution (4000x3000)
- **Frame rate:** Configurable (default 30fps)
- **Duration:** ~44 seconds for 1,317 frames at 30fps

## Project structure

```
Snow-Feb-23/
  build_timelapse.py    # Main script (interactive CLI)
  pyproject.toml        # Project metadata and dependencies
  100GOPRO/             # First batch of GoPro JPGs (not in repo)
  101GOPRO/             # Second batch of GoPro JPGs (not in repo)
  timelapse.mp4         # Output video (not in repo)
```

## Requirements

- Python 3.10+
- Dependencies listed in `pyproject.toml`:
  - **moviepy** — video encoding and clip assembly
  - **Pillow** — image loading and text overlay rendering
  - **numpy** — array handling for frame data
  - **questionary** — interactive terminal prompts

Install with:

```
pip install moviepy Pillow numpy questionary
```

## Usage

Run the script and follow the interactive prompts:

```
python build_timelapse.py
```

The CLI will walk you through each step:

```
=== GoPro Time-Lapse Builder ===

? Source folder (contains GoPro subfolders): .

  Found GoPro subfolders in C:\...\Snow-Feb-23:
    100GOPRO      (999 JPGs)
    101GOPRO      (318 JPGs)

? Select GoPro folders to include:
  > [X] 100GOPRO  (999 JPGs)
    [X] 101GOPRO  (318 JPGs)

? Output filename: timelapse.mp4
? Frames per second: 30

  ============================================
  Source:     C:\...\Snow-Feb-23
  Folders:    100GOPRO, 101GOPRO
  Images:     1317 JPGs
  Time span:  14:53 - 12:49 (21h 56m)
  Output:     timelapse.mp4
  FPS:        30  (43.9 seconds of video)
  ============================================

? Proceed with build? (Y/n)
```

Features:
- **Tab-completion** on the folder path for easy filesystem navigation
- **Auto-detection** of GoPro subfolders (matches `100GOPRO`, `101GOPRO`, etc.)
- **Checkbox selection** with non-empty folders pre-checked
- **Summary review** showing image count, time span, and video duration before building
- **Ctrl+C** exits cleanly at any prompt

## Configuration

Fixed constants at the top of `build_timelapse.py`:

| Variable    | Default          | Description                              |
|-------------|------------------|------------------------------------------|
| `FONT_PATH` | `consola.ttf`    | Font for the timestamp overlay           |
| `FONT_SIZE` | `80`             | Font size in pixels (scaled for 4K)      |

All other settings (source folder, GoPro folders, output filename, FPS) are configured interactively at runtime.

## How it works

1. **Prompt** — Interactive CLI collects source folder, GoPro folder selection, output filename, and FPS.
2. **Detect** — Scans the source folder for subdirectories matching the GoPro naming pattern (`\d{3}GOPRO`).
3. **Gather** — Collects `*.JPG` files from selected subfolders.
4. **Sort** — Orders all images by filesystem last-modified time, preserving capture sequence across folder boundaries.
5. **Overlay** — For each image, reads the file's modification timestamp, formats it as `hh:mm`, and draws it in the lower-right corner with a drop shadow for contrast.
6. **Confirm** — Displays a summary of images, time span, and video duration for review before building.
7. **Encode** — Assembles all frames into an H.264 MP4 using moviepy with multi-threaded encoding.
