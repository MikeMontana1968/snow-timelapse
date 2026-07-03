"""
build_timelapse.py — Combine GoPro time-lapse JPGs into an MP4 with hh:mm overlay.

Interactive CLI prompts for folder selection, output filename, and FPS.

Usage:  python build_timelapse.py
"""

import os, glob, datetime, re, sys, tempfile, shutil, gc, io, contextlib, argparse
import questionary
from questionary import Choice
from PIL import Image, ImageDraw, ImageFont
from PIL.ExifTags import TAGS, GPSTAGS
from moviepy import ImageSequenceClip

try:
    import reverse_geocoder as _rg
    _RG_AVAILABLE = True
except Exception:
    _RG_AVAILABLE = False

# ── Fixed Config ──────────────────────────────────────
FONT_PATH      = r"C:\Windows\Fonts\consola.ttf"
FONT_SIZE      = 80          # good visibility on 4K frames
DEFAULT_FPS    = 30
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
    parent_name = os.path.basename(os.path.normpath(base_dir)) or "timelapse"
    default_output = f"{parent_name}-{datetime.datetime.now().strftime('%b-%d')}.mp4"

    output_name = questionary.text(
        "Output filename:",
        default=default_output,
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


# ── GPS / location ───────────────────────────────────
def _dms_to_deg(dms, ref):
    if not dms or not ref:
        return None
    try:
        d, m, s = (float(x) for x in dms)
    except (TypeError, ValueError):
        return None
    val = d + m / 60 + s / 3600
    if str(ref).upper() in ("S", "W"):
        val = -val
    return val


def get_gps_from_exif(filepath):
    """Return (lat, lon) from a JPG's EXIF, or None."""
    try:
        with Image.open(filepath) as img:
            exif = img._getexif()
        if not exif:
            return None
        gps_ifd = None
        for tag_id, value in exif.items():
            if TAGS.get(tag_id) == "GPSInfo":
                gps_ifd = value
                break
        if not gps_ifd:
            return None
        gps = {GPSTAGS.get(k, k): v for k, v in gps_ifd.items()}
        lat = _dms_to_deg(gps.get("GPSLatitude"), gps.get("GPSLatitudeRef"))
        lon = _dms_to_deg(gps.get("GPSLongitude"), gps.get("GPSLongitudeRef"))
        if lat is None or lon is None:
            return None
        return (lat, lon)
    except Exception:
        return None


def lookup_city(lat, lon):
    """Return 'City, ST' (US) or 'City, CC' string via offline lookup, or None."""
    if not _RG_AVAILABLE:
        return None
    try:
        # reverse_geocoder prints progress on first use; swallow it.
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            results = _rg.search((lat, lon), mode=1)
        if not results:
            return None
        r = results[0]
        city = r.get("name", "").strip()
        admin1 = r.get("admin1", "").strip()
        cc = r.get("cc", "").strip()
        if not city:
            return None
        if cc == "US" and admin1:
            return f"{city}, {admin1}"
        if admin1:
            return f"{city}, {admin1}, {cc}" if cc else f"{city}, {admin1}"
        return f"{city}, {cc}" if cc else city
    except Exception:
        return None


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
def display_summary_and_confirm(base_dir, folders, files, output_path, fps, location=None):
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
    print(f"  Location:   {location or '(no GPS in EXIF)'}")
    print(f"  Output:     {os.path.basename(output_path)}")
    print(f"  FPS:        {fps}  ({duration_secs:.1f} seconds of video)")
    print("  " + "=" * 44)
    print()

    proceed = questionary.confirm("Proceed with build?", default=True).ask()
    if not proceed:
        print("Cancelled.")
        sys.exit(0)


# ── Frame building ───────────────────────────────────
def _draw_stacked(draw, lines, font, anchor_x, anchor_y, align_right, line_gap):
    """Draw stacked text lines with a black shadow. Anchor is the block's corner."""
    dims = []
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        dims.append((bbox[2] - bbox[0], bbox[3] - bbox[1]))
    y = anchor_y
    for line, (tw, th) in zip(lines, dims):
        x = anchor_x - tw if align_right else anchor_x
        draw.text((x + 3, y + 3), line, font=font, fill=(0, 0, 0))
        draw.text((x, y), line, font=font, fill=(255, 255, 255))
        y += th + line_gap
    return sum(h for _, h in dims) + line_gap * (len(lines) - 1)


def build_frames(files, font, temp_dir, location=None):
    """Write overlaid JPGs to temp_dir. Returns the list of output paths."""
    print("Building frames with timestamp overlay...")
    out_paths = []
    total = len(files)
    padding = 30
    line_gap = 8
    base_mtime = os.path.getmtime(files[0])

    for i, filepath in enumerate(files):
        img = Image.open(filepath)
        draw = ImageDraw.Draw(img)

        mtime = os.path.getmtime(filepath)
        dt = datetime.datetime.fromtimestamp(mtime)

        # Bottom-right: date/time + optional location
        br_lines = [dt.strftime("%a %b-%d %H:%M")]
        if location:
            br_lines.append(location)
        # Measure block height so we can bottom-anchor it.
        br_dims = [draw.textbbox((0, 0), l, font=font) for l in br_lines]
        br_total_h = sum(b[3] - b[1] for b in br_dims) + line_gap * (len(br_lines) - 1)
        _draw_stacked(
            draw, br_lines, font,
            anchor_x=img.width - padding,
            anchor_y=img.height - br_total_h - padding,
            align_right=True, line_gap=line_gap,
        )

        # Top-right: elapsed time + frame counter
        elapsed = int(mtime - base_mtime)
        eh, rem = divmod(max(elapsed, 0), 3600)
        em, es = divmod(rem, 60)
        tr_lines = [
            f"et +{eh:02d}:{em:02d}:{es:02d}",
            f"{i + 1:04d}",
        ]
        _draw_stacked(
            draw, tr_lines, font,
            anchor_x=img.width - padding,
            anchor_y=padding,
            align_right=True, line_gap=line_gap,
        )

        out_path = os.path.join(temp_dir, f"frame_{i:06d}.jpg")
        img.save(out_path, "JPEG", quality=92)
        img.close()
        out_paths.append(out_path)

        if (i + 1) % 100 == 0 or i == total - 1:
            print(f"  {i + 1}/{total}")

    return out_paths


# ── Video encoding ───────────────────────────────────
def _write_clip(clip, output_path, codec, preset, ffmpeg_params, threads):
    clip.write_videofile(
        output_path,
        codec=codec,
        preset=preset,
        ffmpeg_params=ffmpeg_params,
        threads=threads,
        logger="bar",
    )


def encode_video(frame_paths, output_path, fps, use_gpu=True):
    """Encode frames to MP4. GPU path uses Intel Quick Sync (h264_qsv); falls back to libx264."""
    clip = ImageSequenceClip(frame_paths, fps=fps)
    try:
        if use_gpu:
            print(f"Encoding video at {fps}fps (GPU: h264_qsv)...")
            try:
                _write_clip(
                    clip, output_path,
                    codec="h264_qsv",
                    preset="veryfast",
                    ffmpeg_params=["-global_quality", "23", "-pix_fmt", "nv12"],
                    threads=4,
                )
            except Exception as e:
                print(f"\nGPU encode failed ({e.__class__.__name__}); falling back to CPU (libx264)...")
                _write_clip(clip, output_path, codec="libx264", preset="medium", ffmpeg_params=None, threads=4)
        else:
            print(f"Encoding video at {fps}fps (CPU: libx264)...")
            _write_clip(clip, output_path, codec="libx264", preset="medium", ffmpeg_params=None, threads=4)
    finally:
        clip.close()
        del clip
        gc.collect()
    print(f"\nDone! Output: {output_path}")
    print(f"Duration: {len(frame_paths)/fps:.1f} seconds ({len(frame_paths)} frames @ {fps}fps)")


# ── Main ─────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(prog="build-timelapse", description="Build a GoPro time-lapse MP4.")
    parser.add_argument("--cpu", action="store_true",
                        help="Force CPU encoding (libx264). Default uses Intel Quick Sync GPU (h264_qsv).")
    args = parser.parse_args()

    print("\n=== GoPro Time-Lapse Builder ===")
    print(f"Encoder: {'CPU (libx264)' if args.cpu else 'GPU (h264_qsv, Intel Quick Sync)'}\n")

    # 1. Pick source folder
    base_dir = prompt_source_folder()

    # 2. Detect and select GoPro subfolders
    gopro_folders = detect_gopro_folders(base_dir)
    selected_folders = prompt_gopro_selection(base_dir, gopro_folders)

    # 3. Output filename and FPS
    output_path, fps = prompt_output_and_fps(base_dir)

    # 4. Gather images
    files = gather_images(base_dir, selected_folders)

    # 5. Try to resolve location from the first image's GPS EXIF
    location = None
    if files:
        gps = get_gps_from_exif(files[0])
        if gps:
            location = lookup_city(*gps)

    # 6. Summary and confirm
    display_summary_and_confirm(base_dir, selected_folders, files, output_path, fps, location=location)

    # 7. Build frames with overlay (streamed to a temp dir to avoid OOM on 4K frames)
    font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
    temp_dir = tempfile.mkdtemp(prefix="timelapse_frames_", dir=base_dir)
    try:
        frame_paths = build_frames(files, font, temp_dir, location=location)

        # 8. Encode video
        encode_video(frame_paths, output_path, fps, use_gpu=not args.cpu)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
