"""
build_timelapse.py — Combine GoPro time-lapse JPGs into an MP4 with hh:mm overlay.

Interactive CLI prompts for folder selection, output filename, and FPS.

Usage:  python build_timelapse.py
"""

import os, glob, datetime, re, sys
import questionary
from questionary import Choice
from PIL import Image, ImageDraw, ImageFont
from moviepy import ImageSequenceClip
import numpy as np

# ── Fixed Config ──────────────────────────────────────
FONT_PATH      = r"C:\Windows\Fonts\consola.ttf"
FONT_SIZE      = 80          # good visibility on 4K frames
DEFAULT_FPS    = 30
DEFAULT_OUTPUT = "timelapse.mp4"
GOPRO_PATTERN  = re.compile(r"^\d{3}GOPRO$", re.IGNORECASE)


# ── Folder detection ─────────────────────────────────
def detect_gopro_folders(base_dir):
    """Scan base_dir for GoPro subfolders. Returns list of (name, jpg_count) tuples."""
    results = []
    for entry in sorted(os.listdir(base_dir)):
        full_path = os.path.join(base_dir, entry)
        if os.path.isdir(full_path) and GOPRO_PATTERN.match(entry):
            jpg_count = len(glob.glob(os.path.join(full_path, "*.JPG")))
            results.append((entry, jpg_count))
    return results


# ── Interactive prompts ──────────────────────────────
def prompt_source_folder():
    """Ask user to select the root folder containing GoPro subfolders."""
    source = questionary.path(
        "Source folder (contains GoPro subfolders):",
        default=".",
        only_directories=True,
        validate=lambda p: True if os.path.isdir(p) else "Not a valid directory",
    ).ask()

    if source is None:
        print("\nCancelled.")
        sys.exit(0)

    return os.path.abspath(source)


def prompt_gopro_selection(base_dir, gopro_folders):
    """Let user pick which GoPro subfolders to include."""
    if not gopro_folders:
        print(f"\n  No GoPro subfolders found in {base_dir}")
        print("  (Looking for folders matching pattern: 100GOPRO, 101GOPRO, etc.)")
        sys.exit(1)

    print(f"\n  Found GoPro subfolders in {base_dir}:")
    for name, count in gopro_folders:
        print(f"    {name:12s}  ({count} JPGs)")
    print()

    choices = []
    for name, count in gopro_folders:
        if count > 0:
            choices.append(Choice(
                title=f"{name}  ({count} JPGs)",
                value=name,
                checked=True,
            ))
        else:
            choices.append(Choice(
                title=f"{name}  (0 JPGs)",
                value=name,
                disabled="No JPGs found",
            ))

    selected = questionary.checkbox(
        "Select GoPro folders to include:",
        choices=choices,
        validate=lambda sel: True if len(sel) > 0 else "Select at least one folder",
    ).ask()

    if selected is None:
        print("\nCancelled.")
        sys.exit(0)

    return selected


def prompt_output_and_fps(base_dir):
    """Prompt for output filename and FPS."""
    output_name = questionary.text(
        "Output filename:",
        default=DEFAULT_OUTPUT,
        validate=lambda v: True if v.lower().endswith(".mp4") else "Filename must end with .mp4",
    ).ask()

    if output_name is None:
        print("\nCancelled.")
        sys.exit(0)

    fps_str = questionary.text(
        "Frames per second:",
        default=str(DEFAULT_FPS),
        validate=lambda v: True if (v.isdigit() and 1 <= int(v) <= 120) else "Enter a number between 1 and 120",
    ).ask()

    if fps_str is None:
        print("\nCancelled.")
        sys.exit(0)

    return os.path.join(base_dir, output_name), int(fps_str)


# ── Image gathering ──────────────────────────────────
def gather_images(base_dir, folder_names):
    """Collect and sort JPGs from the selected GoPro folders."""
    files = []
    for folder in folder_names:
        pattern = os.path.join(base_dir, folder, "*.JPG")
        files.extend(glob.glob(pattern))
    files.sort(key=lambda f: os.path.getmtime(f))
    return files


# ── Summary and confirmation ─────────────────────────
def display_summary_and_confirm(base_dir, folders, files, output_path, fps):
    """Show summary and ask for confirmation before building."""
    if not files:
        print("\n  ERROR: No images found in selected folders!")
        sys.exit(1)

    first_time = datetime.datetime.fromtimestamp(os.path.getmtime(files[0]))
    last_time  = datetime.datetime.fromtimestamp(os.path.getmtime(files[-1]))
    span = last_time - first_time
    hours, remainder = divmod(int(span.total_seconds()), 3600)
    minutes = remainder // 60
    duration_secs = len(files) / fps

    print()
    print("  " + "=" * 44)
    print(f"  Source:     {base_dir}")
    print(f"  Folders:    {', '.join(folders)}")
    print(f"  Images:     {len(files)} JPGs")
    print(f"  Time span:  {first_time.strftime('%H:%M')} - {last_time.strftime('%H:%M')} ({hours}h {minutes:02d}m)")
    print(f"  Output:     {os.path.basename(output_path)}")
    print(f"  FPS:        {fps}  ({duration_secs:.1f} seconds of video)")
    print("  " + "=" * 44)
    print()

    proceed = questionary.confirm("Proceed with build?", default=True).ask()
    if not proceed:
        print("Cancelled.")
        sys.exit(0)


# ── Frame building ───────────────────────────────────
def build_frames(files, font):
    """Build numpy frames with timestamp overlay."""
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

    return frames


# ── Video encoding ───────────────────────────────────
def encode_video(frames, output_path, fps):
    """Encode frames to MP4."""
    print(f"Encoding video at {fps}fps...")
    clip = ImageSequenceClip(frames, fps=fps)
    clip.write_videofile(output_path, codec="libx264", threads=4, logger="bar")
    clip.close()
    print(f"\nDone! Output: {output_path}")
    print(f"Duration: {len(frames)/fps:.1f} seconds ({len(frames)} frames @ {fps}fps)")


# ── Main ─────────────────────────────────────────────
def main():
    print("\n=== GoPro Time-Lapse Builder ===\n")

    # 1. Pick source folder
    base_dir = prompt_source_folder()

    # 2. Detect and select GoPro subfolders
    gopro_folders = detect_gopro_folders(base_dir)
    selected_folders = prompt_gopro_selection(base_dir, gopro_folders)

    # 3. Output filename and FPS
    output_path, fps = prompt_output_and_fps(base_dir)

    # 4. Gather images
    files = gather_images(base_dir, selected_folders)

    # 5. Summary and confirm
    display_summary_and_confirm(base_dir, selected_folders, files, output_path, fps)

    # 6. Build frames with overlay
    font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
    frames = build_frames(files, font)

    # 7. Encode video
    encode_video(frames, output_path, fps)


if __name__ == "__main__":
    main()
