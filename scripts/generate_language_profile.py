#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import os
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

API = "https://api.github.com"
COLORS = {
    "Rust": "#dea584",
    "TypeScript": "#3178c6",
    "JavaScript": "#f1e05a",
    "Python": "#3572A5",
    "CSS": "#663399",
    "HTML": "#e34c26",
    "Shell": "#89e051",
    "Other": "#c9a45a",
}


def get(path: str, token: str):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "rodolfo-profile-metrics",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(API + path, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def render(entries: list[tuple[str, float]], repository_count: int) -> str:
    width, height = 1200, 220
    card_x, card_y = 3, 3
    card_w, card_h = width - 6, height - 6
    bar_x, bar_y, bar_width, bar_height = 54, 58, 1092, 24

    cursor = float(bar_x)
    segments: list[str] = []
    legend: list[str] = []

    for index, (name, percentage) in enumerate(entries):
        segment_width = bar_width * percentage / 100
        color = COLORS.get(name, "#8b6f47")
        segments.append(
            f'<rect x="{cursor:.2f}" y="{bar_y}" width="{segment_width:.2f}" '
            f'height="{bar_height}" fill="{color}"/>'
        )
        cursor += segment_width

        column = index % 4
        row = index // 4
        x = 58 + column * 282
        y = 132 + row * 42
        legend.append(
            f'<circle cx="{x}" cy="{y - 6}" r="6" fill="{color}"/>'
            f'<text x="{x + 17}" y="{y}" class="legend">{html.escape(name)} '
            f'<tspan class="pct">{percentage:.1f}%</tspan></text>'
        )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
<title id="title">Public portfolio code composition</title>
<desc id="desc">Language percentages aggregated from {repository_count} selected public repositories using GitHub language bytes.</desc>
<defs>
  <linearGradient id="bg" x1="0" x2="1">
    <stop offset="0" stop-color="#09080d"/>
    <stop offset=".60" stop-color="#170b12"/>
    <stop offset="1" stop-color="#4b0d1c"/>
  </linearGradient>
</defs>
<style>
  .meta{{font:700 15px Arial,sans-serif;letter-spacing:1.25px;fill:#c9a45a}}
  .legend{{font:700 18px Arial,sans-serif;fill:#f3ead8}}
  .pct{{font-weight:400;fill:#bcae99}}
</style>
<rect x="{card_x}" y="{card_y}" width="{card_w}" height="{card_h}" rx="30" fill="url(#bg)"/>
<rect x="{card_x + 1}" y="{card_y + 1}" width="{card_w - 2}" height="{card_h - 2}" rx="29" fill="none" stroke="#7f5d2f" stroke-opacity=".72"/>
<text x="56" y="32" class="meta">{repository_count} PUBLIC REPOSITORIES · GITHUB LINGUIST BYTES</text>
<clipPath id="barclip"><rect x="{bar_x}" y="{bar_y}" width="{bar_width}" height="{bar_height}" rx="12"/></clipPath>
<rect x="{bar_x}" y="{bar_y}" width="{bar_width}" height="{bar_height}" rx="12" fill="#23141a"/>
<g clip-path="url(#barclip)">{''.join(segments)}</g>
{''.join(legend)}
</svg>"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    config = json.loads(args.config.read_text(encoding="utf-8"))
    username = config["username"]
    token = os.getenv("GITHUB_TOKEN", "")
    excluded = {value.lower() for value in config.get("excludeRepositories", [])}
    totals = defaultdict(int)
    repository_count = 0

    for page in range(1, 11):
        query = urllib.parse.urlencode(
            {"per_page": 100, "page": page, "type": "owner", "sort": "full_name"}
        )
        batch = get(f"/users/{username}/repos?{query}", token)
        for repository in batch:
            if repository["name"].lower() in excluded:
                continue
            if repository.get("fork") or repository.get("archived") or repository.get("disabled"):
                continue
            languages = get(f'/repos/{username}/{repository["name"]}/languages', token)
            if not languages:
                continue
            repository_count += 1
            for language, byte_count in languages.items():
                totals[language] += int(byte_count)
        if len(batch) < 100:
            break

    total_bytes = sum(totals.values())
    if not total_bytes:
        raise SystemExit("No language data returned.")

    ranked = sorted(totals.items(), key=lambda item: (-item[1], item[0].lower()))
    top_count = int(config.get("topLanguages", 6))
    chosen = ranked[:top_count]
    remainder = sum(value for _, value in ranked[top_count:])
    if remainder:
        chosen.append(("Other", remainder))
    entries = [(name, value / total_bytes * 100) for name, value in chosen]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(entries, repository_count), encoding="utf-8")
    print(f"Wrote compact profile composition to {args.output} from {repository_count} repositories.")


if __name__ == "__main__":
    main()
