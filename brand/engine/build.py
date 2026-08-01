#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import os
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "brand" / "config"
OUT = ROOT / "assets" / "generated"
QA_PATH = OUT / "QA-REPORT.json"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def font_match(family: str) -> Path | None:
    try:
        result = subprocess.run(
            ["fc-match", "-f", "%{family[0]}|%{file}\\n", family],
            capture_output=True,
            check=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None

    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not lines or "|" not in lines[0]:
        return None

    resolved_family, resolved_file = lines[0].split("|", 1)
    normalize = lambda value: "".join(ch for ch in value.lower() if ch.isalnum())
    requested = normalize(family)
    resolved = normalize(resolved_family)
    if requested not in resolved and resolved not in requested:
        return None

    path = Path(resolved_file)
    return path if path.is_file() else None


def resolve_font(path_env: str, family_env: str, fallbacks: list[str]) -> Path:
    explicit = os.getenv(path_env, "").strip()
    if explicit:
        path = Path(explicit).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"{path_env} points to a missing file: {path}")
        return path

    preferred = os.getenv(family_env, "").strip()
    for family in ([preferred] if preferred else []) + fallbacks:
        path = font_match(family)
        if path:
            return path

    raise RuntimeError(f"No usable font found for {family_env}")


def fit_font(path: Path, value: str, max_size: int, max_width: int, min_size: int = 8) -> ImageFont.FreeTypeFont:
    for size in range(max_size, min_size - 1, -1):
        font = ImageFont.truetype(str(path), size)
        box = font.getbbox(value)
        if box[2] - box[0] <= max_width:
            return font
    return ImageFont.truetype(str(path), min_size)


@dataclass
class QaCheck:
    asset: str
    check: str
    passed: bool
    detail: str


QA: list[QaCheck] = []


def add_check(asset: str, check: str, passed: bool, detail: str) -> None:
    QA.append(QaCheck(asset, check, passed, detail))
    if not passed:
        raise RuntimeError(f"QA failed for {asset}: {check}: {detail}")


def text_box(draw: ImageDraw.ImageDraw, xy: tuple[int, int], value: str, font: ImageFont.FreeTypeFont) -> tuple[int, int, int, int]:
    x, y = xy
    box = draw.textbbox((x, y), value, font=font, anchor="lt")
    return tuple(int(v) for v in box)


def draw_text_safe(
    draw: ImageDraw.ImageDraw,
    asset: str,
    label: str,
    xy: tuple[int, int],
    value: str,
    font: ImageFont.FreeTypeFont,
    fill: tuple[int, int, int],
    safe: tuple[int, int, int, int],
    anchor: str = "lt",
) -> tuple[int, int, int, int]:
    draw.text(xy, value, font=font, fill=fill, anchor=anchor)
    box = draw.textbbox(xy, value, font=font, anchor=anchor)
    left, top, right, bottom = safe
    passed = box[0] >= left and box[1] >= top and box[2] <= right and box[3] <= bottom
    add_check(asset, f"text:{label}", passed, f"bbox={tuple(map(int, box))}, safe={safe}")
    return tuple(map(int, box))


def gradient(width: int, height: int, theme: dict, light: bool = False) -> Image.Image:
    if light:
        left, middle, right = (244, 239, 231), (234, 223, 211), (218, 197, 184)
    else:
        left = rgb(theme["background"])
        middle = rgb(theme["background2"])
        right = rgb(theme["oxblood"])

    image = Image.new("RGB", (width, height))
    pixels = image.load()
    for x in range(width):
        progress = x / max(1, width - 1)
        if progress < 0.55:
            t = progress / 0.55
            color = tuple(round(left[i] + (middle[i] - left[i]) * t) for i in range(3))
        else:
            t = (progress - 0.55) / 0.45
            color = tuple(round(middle[i] + (right[i] - middle[i]) * t) for i in range(3))
        for y in range(height):
            pixels[x, y] = color

    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    radius = int(min(width, height) * 0.85)
    cx, cy = int(width * 0.78), int(height * 0.30)
    glow_draw.ellipse(
        (cx - radius, cy - radius, cx + radius, cy + radius),
        fill=(*rgb(theme["signal"]), 82),
    )
    glow = glow.filter(ImageFilter.GaussianBlur(max(16, int(height * 0.12))))
    image = Image.alpha_composite(image.convert("RGBA"), glow)

    grid = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    grid_draw = ImageDraw.Draw(grid)
    step = max(24, int(width / 30))
    grid_color = (*rgb(theme["gold"]), 16)
    for x in range(0, width, step):
        grid_draw.line((x, 0, x, height), fill=grid_color, width=1)
    for y in range(0, height, step):
        grid_draw.line((0, y, width, y), fill=grid_color, width=1)
    return Image.alpha_composite(image, grid)


def orbit_layer(size: int, theme: dict, angle: float, letter: str, display_path: Path) -> Image.Image:
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    center = size // 2
    gold = rgb(theme["gold"])
    gold_hi = rgb(theme["goldHighlight"])

    draw.ellipse(
        (center - size * .34, center - size * .34, center + size * .34, center + size * .34),
        outline=(*gold, 70), width=max(1, size // 170),
    )
    draw.ellipse(
        (center - size * .23, center - size * .23, center + size * .23, center + size * .23),
        outline=(*gold, 110), width=max(1, size // 170),
    )

    for rotation, alpha in [(-16 + angle, 155), (35 - angle * .55, 105)]:
        temp = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        temp_draw = ImageDraw.Draw(temp)
        temp_draw.ellipse(
            (center - size * .43, center - size * .12, center + size * .43, center + size * .12),
            outline=(*gold_hi, alpha), width=max(2, size // 125),
        )
        temp = temp.rotate(rotation, resample=Image.Resampling.BICUBIC, center=(center, center))
        layer = Image.alpha_composite(layer, temp)

    draw = ImageDraw.Draw(layer)
    theta = math.radians(angle * 2.2)
    node_x = center + math.cos(theta) * size * .39
    node_y = center + math.sin(theta) * size * .16
    draw.ellipse(
        (node_x - size * .012, node_y - size * .012, node_x + size * .012, node_y + size * .012),
        fill=gold_hi,
    )

    shield = [
        (center, center - size * .24),
        (center + size * .12, center - size * .17),
        (center + size * .12, center + size * .06),
        (center, center + size * .14),
        (center - size * .12, center + size * .06),
        (center - size * .12, center - size * .17),
    ]
    draw.polygon(shield, fill=rgb("#170910"), outline=gold_hi)
    font = ImageFont.truetype(str(display_path), int(size * .18))
    box = draw.textbbox((0, 0), letter, font=font)
    draw.text(
        (center - (box[2] - box[0]) / 2, center - (box[3] - box[1]) / 2 - size * .035),
        letter, font=font, fill=gold_hi,
    )
    return layer


def save_full_bleed(image: Image.Image, path: Path, expected: tuple[int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = image.convert("RGB")
    add_check(path.name, "dimensions", image.size == expected, f"actual={image.size}, expected={expected}")
    corners = [image.getpixel((0, 0)), image.getpixel((image.width - 1, 0)), image.getpixel((0, image.height - 1)), image.getpixel((image.width - 1, image.height - 1))]
    no_white = all(max(pixel) < 245 for pixel in corners)
    add_check(path.name, "full_bleed_no_white_corners", no_white, f"corners={corners}")
    if path.suffix.lower() in {".jpg", ".jpeg"}:
        image.save(path, "JPEG", quality=94, optimize=True, subsampling=0)
    else:
        image.save(path, "PNG", optimize=True)


def save_rounded_card(image: Image.Image, path: Path, expected: tuple[int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = image.convert("RGBA")
    add_check(path.name, "dimensions", image.size == expected, f"actual={image.size}, expected={expected}")
    corners = [
        image.getpixel((0, 0))[3],
        image.getpixel((image.width - 1, 0))[3],
        image.getpixel((0, image.height - 1))[3],
        image.getpixel((image.width - 1, image.height - 1))[3],
    ]
    add_check(path.name, "transparent_rounded_corners", all(alpha == 0 for alpha in corners), f"corner_alpha={corners}")
    image.save(path, "PNG", optimize=True, compress_level=9)


def build_hero(brand: dict, display: Path, serif: Path, tech: Path, light: bool = False, angle: float = 0) -> Image.Image:
    asset = "github-hero-light" if light else "github-hero-dark"
    theme = brand["theme"]
    identity = brand["identity"]
    width, height = 2400, 900
    image = gradient(width, height, theme, light)
    draw = ImageDraw.Draw(image)

    gold = rgb(theme["gold"])
    gold_hi = rgb(theme["goldHighlight"])
    ivory = rgb("#241116" if light else theme["ivory"])
    muted = rgb("#4d3638" if light else theme["muted"])

    frame = (48, 48, width - 48, height - 48)
    draw.rectangle(frame, outline=(*gold, 95), width=2)
    safe = (120, 105, 1200, 825)

    eyebrow = fit_font(tech, identity["eyebrow"], 32, 1060)
    name1 = fit_font(display, "RODOLFO P.", 132, 1060)
    name2 = fit_font(display, "RODRIGUES", 132, 1060)
    role_font = fit_font(serif, identity["roles"][0], 45, 1060)
    domains_value = " · ".join(identity["domains"])
    domains_font = fit_font(tech, domains_value, 30, 1060)

    draw_text_safe(draw, asset, "eyebrow", (142, 135), identity["eyebrow"], eyebrow, gold, safe)
    draw_text_safe(draw, asset, "name1", (142, 245), "RODOLFO P.", name1, ivory, safe)
    draw_text_safe(draw, asset, "name2", (142, 385), "RODRIGUES", name2, gold_hi, safe)
    draw_text_safe(draw, asset, "role1", (148, 585), identity["roles"][0], role_font, muted, safe)
    draw_text_safe(draw, asset, "role2", (148, 647), identity["roles"][1], role_font, muted, safe)
    draw.line((148, 725, 1125, 725), fill=(*gold, 125), width=3)
    draw_text_safe(draw, asset, "domains", (148, 755), domains_value, domains_font, gold_hi, safe)

    image.alpha_composite(orbit_layer(720, theme, angle, "R", display), (1460, 75))
    return image


def build_architecture(brand: dict, serif: Path, tech: Path) -> Image.Image:
    asset = "github-architecture"
    theme = brand["theme"]
    width, height = 2400, 600
    image = gradient(width, height, theme)
    draw = ImageDraw.Draw(image)
    gold = rgb(theme["gold"])
    gold_hi = rgb(theme["goldHighlight"])
    ivory = rgb(theme["ivory"])
    muted = rgb(theme["muted"])

    draw.rectangle((36, 36, width - 36, height - 36), outline=(*gold, 75), width=2)
    safe = (70, 55, width - 70, height - 55)
    header = fit_font(tech, "AUTHORITY FLOWS DOWN · EVIDENCE FLOWS UP", 30, 1500)
    draw_text_safe(draw, asset, "header", (100, 72), "AUTHORITY FLOWS DOWN · EVIDENCE FLOWS UP", header, gold, safe)

    columns = [
        ("FRONTEND", "React · TypeScript", "Interaction · State · Visualization"),
        ("BOUNDARY", "Services · Contracts", "IPC · HTTP · Validation · Events"),
        ("BACKEND", "Rust · Node.js · AI", "Authority · Security · Orchestration"),
        ("DATA", "Operational · Analytical", "Evidence · Semantic · Graph"),
    ]
    box_width, box_height, y = 500, 310, 175
    start_x, gap = 90, 66
    label_font = ImageFont.truetype(str(tech), 28)
    title_font = ImageFont.truetype(str(serif), 42)
    detail_font = ImageFont.truetype(str(tech), 26)

    for index, (label, title, detail) in enumerate(columns):
        x = start_x + index * (box_width + gap)
        draw.rounded_rectangle((x, y, x + box_width, y + box_height), radius=28, fill=rgb("#241018"), outline=gold, width=2)
        card_safe = (x + 34, y + 30, x + box_width - 34, y + box_height - 30)
        draw_text_safe(draw, asset, f"{label}:label", (x + 38, y + 42), label, label_font, gold, card_safe)
        fitted_title = fit_font(serif, title, 42, box_width - 76, min_size=30)
        draw_text_safe(draw, asset, f"{label}:title", (x + 38, y + 112), title, fitted_title, ivory, card_safe)
        fitted_detail = fit_font(tech, detail, 26, box_width - 76, min_size=19)
        draw_text_safe(draw, asset, f"{label}:detail", (x + 38, y + 208), detail, fitted_detail, muted, card_safe)
        if index < 3:
            arrow_x = x + box_width + 12
            center_y = y + box_height // 2
            draw.line((arrow_x, center_y, arrow_x + 30, center_y), fill=gold_hi, width=10)
            draw.polygon([(arrow_x + 30, center_y - 22), (arrow_x + 60, center_y), (arrow_x + 30, center_y + 22)], fill=gold_hi)
    return image


def build_project_card(brand: dict, system: dict, display: Path, tech: Path) -> Image.Image:
    asset = f"project-{system['id']}"
    theme = brand["theme"]
    width, height = 1200, 600

    # Build the visual surface first, then clip the entire card to a true
    # rounded alpha mask. GitHub cannot apply CSS border radius to README
    # images, so the asset itself owns its corners.
    surface = gradient(width, height, theme).convert("RGBA")
    mask = Image.new("L", (width, height), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle((2, 2, width - 3, height - 3), radius=52, fill=255)
    surface.putalpha(mask)
    image = surface

    draw = ImageDraw.Draw(image)
    gold = rgb(theme["gold"])
    gold_hi = rgb(theme["goldHighlight"])
    ivory = rgb(theme["ivory"])
    muted = rgb(theme["muted"])

    # One deliberate perimeter instead of a square table cell plus nested box.
    draw.rounded_rectangle(
        (3, 3, width - 4, height - 4),
        radius=50,
        outline=(*gold, 120),
        width=3,
    )

    safe = (72, 58, 760, 548)
    eyebrow = system.get("eyebrow", "PUBLIC SYSTEM")
    title_font = fit_font(display, system["title"], 78, 680, min_size=52)
    subtitle_font = fit_font(tech, system["subtitle"], 30, 680, min_size=21)

    draw_text_safe(
        draw,
        asset,
        "eyebrow",
        (78, 72),
        eyebrow,
        fit_font(tech, eyebrow, 22, 680),
        gold,
        safe,
    )
    draw.line((78, 112, 282, 112), fill=(*gold, 85), width=2)
    draw_text_safe(draw, asset, "title", (78, 330), system["title"], title_font, ivory, safe)
    draw_text_safe(draw, asset, "subtitle", (78, 440), system["subtitle"], subtitle_font, gold_hi, safe)
    draw.line((78, 526, 640, 526), fill=(*gold, 90), width=3)

    icon_id = system.get("icon", system["id"])
    icon_path = ROOT / "brand" / "source" / "project-icons" / f"{icon_id}.png"
    if icon_path.is_file():
        icon = Image.open(icon_path).convert("RGBA")
        icon.thumbnail((390, 390), Image.Resampling.LANCZOS)
        x = 790 + (390 - icon.width) // 2
        y = 98 + (390 - icon.height) // 2
        image.alpha_composite(icon, (x, y))
        add_check(asset, "project icon", True, f"{icon_path.name} loaded at {icon.width}x{icon.height}")
    else:
        image.alpha_composite(orbit_layer(400, theme, 0, system["letter"], display), (780, 50))
        add_check(asset, "project icon fallback", True, f"No icon for {icon_id}; orbital letter used")

    return image


def build_linkedin_personal(brand: dict, display: Path, serif: Path, tech: Path) -> Image.Image:
    asset = "linkedin-personal-cover"
    theme = brand["theme"]
    identity = brand["identity"]
    width, height = 1584, 396
    image = gradient(width, height, theme)
    draw = ImageDraw.Draw(image)
    gold = rgb(theme["gold"])
    gold_hi = rgb(theme["goldHighlight"])
    ivory = rgb(theme["ivory"])
    muted = rgb(theme["muted"])

    x = 420
    safe = (400, 34, 1210, 360)
    role = "BUSINESS SYSTEMS ARCHITECT · FULL-STACK AI DEVELOPER"
    domains = " · ".join(identity["domains"])
    draw_text_safe(draw, asset, "eyebrow", (x, 54), identity["eyebrow"], fit_font(tech, identity["eyebrow"], 21, 760), gold, safe)
    draw_text_safe(draw, asset, "name", (x, 115), identity["name"].upper(), fit_font(display, identity["name"].upper(), 54, 790), ivory, safe)
    draw_text_safe(draw, asset, "role", (x, 190), role, fit_font(serif, role, 25, 790), muted, safe)
    draw.line((x, 252, x + 690, 252), fill=(*gold, 120), width=2)
    draw_text_safe(draw, asset, "domains", (x, 279), domains, fit_font(tech, domains, 19, 790), gold_hi, safe)
    image.alpha_composite(orbit_layer(330, theme, 0, "R", display), (1220, 30))
    return image


def build_linkedin_business(brand: dict, display: Path, serif: Path, tech: Path) -> Image.Image:
    asset = "linkedin-business-cover"
    theme = brand["theme"]
    identity = brand["identity"]
    width, height = 4200, 700
    image = gradient(width, height, theme)
    draw = ImageDraw.Draw(image)
    gold = rgb(theme["gold"])
    gold_hi = rgb(theme["goldHighlight"])
    ivory = rgb(theme["ivory"])
    muted = rgb(theme["muted"])

    x = 1250
    safe = (1220, 55, 3290, 650)
    headline = "BUSINESS SYSTEMS"
    subtitle = "Finance · Inventory · Operations Intelligence"
    architecture = "ARCHITECTURE · AUTHORITY · EVIDENCE · DECISION"
    draw_text_safe(draw, asset, "identity", (x, 75), identity["name"].upper(), fit_font(tech, identity["name"].upper(), 48, 1900), gold, safe)
    draw_text_safe(draw, asset, "headline", (x, 180), headline, fit_font(display, headline, 185, 1900), ivory, safe)
    draw_text_safe(draw, asset, "subtitle", (x, 385), subtitle, fit_font(serif, subtitle, 76, 1900), muted, safe)
    draw.line((x, 505, x + 1750, 505), fill=(*gold, 120), width=3)
    draw_text_safe(draw, asset, "architecture", (x, 548), architecture, fit_font(tech, architecture, 46, 1900), gold_hi, safe)
    image.alpha_composite(orbit_layer(600, theme, 0, "R", display), (3450, 48))
    return image


def build_google(brand: dict, display: Path, serif: Path, tech: Path) -> Image.Image:
    asset = "google-business-cover"
    theme = brand["theme"]
    identity = brand["identity"]
    width, height = 1024, 576
    image = gradient(width, height, theme)
    draw = ImageDraw.Draw(image)
    gold = rgb(theme["gold"])
    gold_hi = rgb(theme["goldHighlight"])
    ivory = rgb(theme["ivory"])
    muted = rgb(theme["muted"])
    safe = (48, 55, 650, 510)
    x = 58
    domains = "FINANCE · INVENTORY · DATA · AI"
    tagline = "Operational intelligence for real business decisions."
    draw_text_safe(draw, asset, "eyebrow", (x, 82), identity["eyebrow"], fit_font(tech, identity["eyebrow"], 19, 590), gold, safe)
    draw_text_safe(draw, asset, "name", (x, 175), identity["name"].upper(), fit_font(display, identity["name"].upper(), 56, 560), ivory, safe)
    draw_text_safe(draw, asset, "domains", (x, 265), domains, fit_font(tech, domains, 22, 600), gold_hi, safe)
    draw_text_safe(draw, asset, "tagline", (x, 340), tagline, fit_font(serif, tagline, 29, 600), muted, safe)
    image.alpha_composite(orbit_layer(390, theme, 0, "R", display), (640, 80))
    return image


def build_instagram(brand: dict, display: Path, serif: Path, tech: Path) -> Image.Image:
    asset = "instagram-feed"
    theme = brand["theme"]
    identity = brand["identity"]
    width, height = 1080, 1350
    image = gradient(width, height, theme)
    draw = ImageDraw.Draw(image)
    gold = rgb(theme["gold"])
    gold_hi = rgb(theme["goldHighlight"])
    ivory = rgb(theme["ivory"])
    muted = rgb(theme["muted"])
    image.alpha_composite(orbit_layer(650, theme, 0, "R", display), (215, 95))
    safe = (90, 700, 990, 1250)
    draw_text_safe(draw, asset, "line1", (540, 790), "BUSINESS LOGIC,", fit_font(display, "BUSINESS LOGIC,", 76, 850), ivory, safe, anchor="ma")
    draw_text_safe(draw, asset, "line2", (540, 900), "MADE OPERATIONAL.", fit_font(display, "MADE OPERATIONAL.", 76, 850), gold_hi, safe, anchor="ma")
    draw.line((230, 1000, 850, 1000), fill=(*gold, 120), width=3)
    domains = "FINANCE · INVENTORY · AI · INTERACTIVE PRODUCTS"
    draw_text_safe(draw, asset, "domains", (540, 1045), domains, fit_font(tech, domains, 22, 820), muted, safe, anchor="ma")
    draw_text_safe(draw, asset, "identity", (540, 1160), identity["name"].upper(), fit_font(serif, identity["name"].upper(), 32, 820), gold_hi, safe, anchor="ma")
    return image


def build_readme(brand: dict, systems: list[dict]) -> str:
    identity = brand["identity"]
    hero = "./assets/generated/github/hero-motion.gif" if brand["motion"]["enabled"] else "./assets/generated/github/hero-dark.png"
    visible = sorted(
        [system for system in systems if system.get("profileVisible", False)],
        key=lambda system: system.get("profileOrder", 999),
    )

    cards: list[str] = []
    descriptions: list[str] = []
    for system in visible:
        card = (
            f'<img alt="{system["title"]}" '
            f'src="./assets/generated/projects/{system["id"]}.png" width="49%">'
        )
        if system.get("url"):
            card = f'<a href="{system["url"]}">{card}</a>'
        cards.append(card)
        descriptions.append(f'- **{system["title"]}**: {system["description"]}')

    card_gallery = (
        '<p align="center">\n  '
        + '\n  '.join(cards)
        + '\n</p>'
    )
    description_list = '\n'.join(descriptions)

    return f"""<img alt="{identity["name"]}" src="{hero}" width="100%">

<p align="center"><strong>Business Systems Architect · Full-Stack AI Developer</strong></p>

<p align="center">I turn operational problems into inspectable software for finance, inventory, AI workloads, and interactive worlds.</p>

<p align="center">
  <a href="{brand["links"]["portfolio"]}">Portfolio</a> ·
  <a href="{brand["links"]["repositories"]}">Repositories</a> ·
  {identity["location"]}
</p>

## Selected public systems

{card_gallery}

{description_list}

## Public portfolio code composition

<p align="center">
  <img alt="Automatically updated programming-language composition across public repositories" src="./assets/generated/profile/languages.svg" width="100%">
</p>

<sub>Calculated from GitHub Linguist language bytes across selected public, non-fork repositories. This describes the visible portfolio, not personal proficiency.</sub>

## How I work

I began with operations and business problems rather than a preferred framework. I map the decisions, evidence, authority, and failure points first; the stack comes second.

<p align="center"><img alt="Frontend to backend architecture boundary" src="./assets/generated/github/architecture-boundary.png" width="100%"></p>

## Decision-system loop

<p align="center">
  <img alt="Animated loop from business modelling through governance, observation, and improvement" src="./assets/generated/github/decision-system-loop.gif" width="100%">
</p>

## Current direction

I am turning private architectural work into focused public showcases and commercial products while continuing development of **The Quiet Ledger**.
"""


def write_qa_report(fonts: dict[str, str]) -> None:
    failures = [check for check in QA if not check.passed]
    report = {
        "version": "3.1.0",
        "passed": not failures,
        "fonts": fonts,
        "checks": [asdict(check) for check in QA],
    }
    QA_PATH.parent.mkdir(parents=True, exist_ok=True)
    QA_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")


def build_all(animate: bool = False) -> None:
    QA.clear()
    brand = read_json(CONFIG / "brand.json")
    systems = read_json(CONFIG / "systems.json")
    fonts = brand["fonts"]
    display = resolve_font("DISPLAY_FONT_PATH", "DISPLAY_FONT_FAMILY", fonts["displayFamilies"])
    serif = resolve_font("SERIF_FONT_PATH", "SERIF_FONT_FAMILY", fonts["serifFamilies"])
    tech = resolve_font("TECH_FONT_PATH", "TECH_FONT_FAMILY", fonts["technicalFamilies"])

    print(f"Display: {display}")
    print(f"Serif:   {serif}")
    print(f"Tech:    {tech}")

    for path in [
        OUT / "github", OUT / "projects", OUT / "social/linkedin-personal",
        OUT / "social/linkedin-business", OUT / "social/instagram", OUT / "social/google-business", OUT / "profile",
    ]:
        path.mkdir(parents=True, exist_ok=True)

    save_full_bleed(build_hero(brand, display, serif, tech), OUT / "github/hero-dark.png", (2400, 900))
    save_full_bleed(build_hero(brand, display, serif, tech, light=True), OUT / "github/hero-light.png", (2400, 900))
    save_full_bleed(build_architecture(brand, serif, tech), OUT / "github/architecture-boundary.png", (2400, 600))

    for system in systems:
        save_rounded_card(build_project_card(brand, system, display, tech), OUT / f"projects/{system['id']}.png", (1200, 600))

    personal = build_linkedin_personal(brand, display, serif, tech)
    save_full_bleed(personal, OUT / "social/linkedin-personal/linkedin-personal-cover-1584x396.jpg", (1584, 396))
    save_full_bleed(personal, OUT / "social/linkedin-personal/linkedin-personal-cover-1584x396.png", (1584, 396))

    business = build_linkedin_business(brand, display, serif, tech)
    save_full_bleed(business, OUT / "social/linkedin-business/linkedin-business-cover-4200x700.jpg", (4200, 700))
    save_full_bleed(business, OUT / "social/linkedin-business/linkedin-business-cover-4200x700.png", (4200, 700))

    google = build_google(brand, display, serif, tech)
    save_full_bleed(google, OUT / "social/google-business/google-business-cover-1024x576.jpg", (1024, 576))
    save_full_bleed(google, OUT / "social/google-business/google-business-cover-1024x576.png", (1024, 576))

    save_full_bleed(build_instagram(brand, display, serif, tech), OUT / "social/instagram/instagram-feed-1080x1350.png", (1080, 1350))

    if animate or brand["motion"]["enabled"]:
        frames: list[Image.Image] = []
        count = int(brand["motion"]["frames"])
        for index in range(count):
            frame = build_hero(brand, display, serif, tech, angle=index * (360 / count)).resize((1200, 450), Image.Resampling.LANCZOS)
            frames.append(frame.convert("P", palette=Image.Palette.ADAPTIVE, colors=128))
        frames[0].save(
            OUT / "github/hero-motion.gif", save_all=True, append_images=frames[1:],
            duration=int(brand["motion"]["durationMs"]), loop=0, optimize=True, disposal=2,
        )

    ROOT.joinpath("README.md").write_text(build_readme(brand, systems), encoding="utf-8")
    write_qa_report({"display": str(display), "serif": str(serif), "technical": str(tech)})
    print(f"Brand build complete. QA checks: {len(QA)}")


if __name__ == "__main__":
    build_all(animate="--animate" in os.sys.argv)
