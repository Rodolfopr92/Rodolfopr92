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

    width, height = 1200, 350
    bar_x, bar_y, bar_width, bar_height = 60, 126, 1080, 28
    cursor = float(bar_x)
    segments = []
    legend = []

    for index, (name, percentage) in enumerate(entries):
        segment_width = bar_width * percentage / 100
        color = COLORS.get(name, "#8b6f47")
        segments.append(
            f'<rect x="{cursor:.2f}" y="{bar_y}" width="{segment_width:.2f}" '
            f'height="{bar_height}" fill="{color}"/>'
        )
        cursor += segment_width

        column = index % 3
        row = index // 3
        x = 65 + column * 355
        y = 210 + row * 58
        legend.append(
            f'<circle cx="{x}" cy="{y - 6}" r="7" fill="{color}"/>'
            f'<text x="{x + 18}" y="{y}" class="legend">{html.escape(name)} '
            f'<tspan class="pct">{percentage:.1f}%</tspan></text>'
        )

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">
<defs><linearGradient id="bg"><stop stop-color="#08080d"/><stop offset="1" stop-color="#4b0d1c"/></linearGradient></defs>
<style>.title{{font:700 34px Georgia,serif;fill:#f3ead8}}.subtitle{{font:18px Arial;fill:#bcae99}}.legend{{font:700 20px Arial;fill:#f3ead8}}.pct{{font-weight:400;fill:#bcae99}}</style>
<rect width="{width}" height="{height}" rx="22" fill="url(#bg)"/>
<rect x="18" y="18" width="{width - 36}" height="{height - 36}" rx="18" fill="none" stroke="#7f5d2f"/>
<text x="60" y="66" class="title">Public portfolio code composition</text>
<text x="60" y="96" class="subtitle">Aggregated from {repository_count} selected public repositories using GitHub language bytes.</text>
<clipPath id="clip"><rect x="{bar_x}" y="{bar_y}" width="{bar_width}" height="{bar_height}" rx="14"/></clipPath>
<g clip-path="url(#clip)">{''.join(segments)}</g>
{''.join(legend)}
</svg>"""

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(svg, encoding="utf-8")
    print(f"Wrote {args.output} from {repository_count} repositories.")


if __name__ == "__main__":
    main()
