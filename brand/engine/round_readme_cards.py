#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from PIL import Image, ImageChops, ImageDraw, ImageSequence

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ASSETS = (
    ROOT / "assets/generated/github/hero-dark.png",
    ROOT / "assets/generated/github/hero-light.png",
    ROOT / "assets/generated/github/architecture-boundary.png",
    ROOT / "assets/generated/github/decision-system-loop.gif",
)


def radius_for(size: tuple[int, int]) -> int:
    return max(24, round(min(size) * 0.085))


def rounded_rgba(image: Image.Image, radius: int | None = None) -> Image.Image:
    rgba = image.convert("RGBA")
    width, height = rgba.size
    radius = radius if radius is not None else radius_for(rgba.size)
    mask = Image.new("L", rgba.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (1, 1, width - 2, height - 2),
        radius=radius,
        fill=255,
    )
    rgba.putalpha(ImageChops.multiply(rgba.getchannel("A"), mask))
    return rgba


def corner_alpha(image: Image.Image) -> tuple[int, int, int, int]:
    rgba = image.convert("RGBA")
    width, height = rgba.size
    return (
        rgba.getpixel((0, 0))[3],
        rgba.getpixel((width - 1, 0))[3],
        rgba.getpixel((0, height - 1))[3],
        rgba.getpixel((width - 1, height - 1))[3],
    )


def png_is_rounded(path: Path) -> bool:
    with Image.open(path) as image:
        return all(alpha == 0 for alpha in corner_alpha(image))


def round_png_file(path: Path) -> bool:
    if not path.is_file():
        return False
    with Image.open(path) as image:
        if all(alpha == 0 for alpha in corner_alpha(image)):
            return False
        rounded = rounded_rgba(image)
    with NamedTemporaryFile(dir=path.parent, suffix=".png", delete=False) as handle:
        temporary = Path(handle.name)
    try:
        rounded.save(temporary, "PNG", optimize=True, compress_level=9)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return True


def gif_is_rounded(path: Path) -> bool:
    with Image.open(path) as source:
        if getattr(source, "n_frames", 1) < 2:
            return False
        for frame in ImageSequence.Iterator(source):
            if not all(alpha == 0 for alpha in corner_alpha(frame)):
                return False
    return True


def _palette_frame(rgba: Image.Image) -> Image.Image:
    rgb = Image.new("RGB", rgba.size, (0, 0, 0))
    rgb.paste(rgba, mask=rgba.getchannel("A"))
    palette = rgb.convert("P", palette=Image.Palette.ADAPTIVE, colors=255)
    transparent_pixels = rgba.getchannel("A").point(lambda alpha: 255 if alpha < 128 else 0)
    palette.paste(255, mask=transparent_pixels)
    palette.info["transparency"] = 255
    return palette


def round_gif_file(path: Path) -> bool:
    if not path.is_file():
        return False
    if gif_is_rounded(path):
        return False

    with Image.open(path) as source:
        loop = int(source.info.get("loop", 0))
        default_duration = int(source.info.get("duration", 100))
        frames: list[Image.Image] = []
        durations: list[int] = []
        for frame in ImageSequence.Iterator(source):
            rounded = rounded_rgba(frame.copy().convert("RGBA"))
            frames.append(_palette_frame(rounded))
            durations.append(int(frame.info.get("duration", default_duration)))

    if len(frames) < 2:
        raise RuntimeError(f"Animated asset lost its frames: {path}")

    with NamedTemporaryFile(dir=path.parent, suffix=".gif", delete=False) as handle:
        temporary = Path(handle.name)
    try:
        frames[0].save(
            temporary,
            "GIF",
            save_all=True,
            append_images=frames[1:],
            duration=durations,
            loop=loop,
            transparency=255,
            disposal=2,
            optimize=False,
        )
        with Image.open(temporary) as verification:
            if getattr(verification, "n_frames", 1) != len(frames):
                raise RuntimeError(
                    f"Frame count changed for {path}: expected {len(frames)}, got {getattr(verification, 'n_frames', 1)}"
                )
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return True


def check_asset(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.suffix.lower() == ".gif":
        if not gif_is_rounded(path):
            raise RuntimeError(f"GIF corners are not transparent across every frame: {path}")
    elif not png_is_rounded(path):
        raise RuntimeError(f"PNG corners are not transparent: {path}")


def process_asset(path: Path) -> bool:
    if path.suffix.lower() == ".gif":
        return round_gif_file(path)
    return round_png_file(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("paths", nargs="*", type=Path)
    args = parser.parse_args()
    paths = tuple(args.paths) or DEFAULT_ASSETS

    for path in paths:
        if args.check:
            check_asset(path)
            print(f"PASS {path.relative_to(ROOT)}")
        else:
            changed = process_asset(path)
            print(f"{'ROUNDED' if changed else 'UNCHANGED'} {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
