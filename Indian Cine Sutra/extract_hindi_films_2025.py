#!/usr/bin/env python3
"""Extract Hindi film data for 2025 from Wikipedia into a single JSON file."""

from __future__ import annotations

import json
import re
from datetime import datetime
from html import unescape
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

SOURCE_URL = "https://en.wikipedia.org/wiki/List_of_Hindi_films_of_2025"
OUTPUT_PATH = Path(__file__).resolve().parent / "hindi_films_2025.json"


def fetch_html(url: str) -> str:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="ignore")


def strip_tags(html_fragment: str) -> str:
    text = re.sub(r"<sup[^>]*>.*?</sup>", "", html_fragment, flags=re.S)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_release_date(raw_text: str) -> str:
    clean = raw_text.strip()
    match = re.search(r"(\d{1,2}\s+[A-Za-z]+\s+\d{4})", clean)
    if match:
        clean = match.group(1)

    for fmt in ("%d %B %Y", "%d %b %Y"):
        try:
            return datetime.strptime(clean, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue

    return clean


def split_list(raw_text: str) -> list[str]:
    parts = re.split(r"\s*(?:,|/|\n|•|·)\s*", raw_text)
    return [part.strip() for part in parts if part.strip()]


def extract_reference_labels(cell_html: str) -> list[str]:
    labels: list[str] = []
    for sup in re.findall(r"<sup[^>]*class=\"reference\"[^>]*>(.*?)</sup>", cell_html, flags=re.S):
        labels.extend(re.findall(r"\d+", unescape(sup)))
    if labels:
        return labels
    return re.findall(r"\d+", strip_tags(cell_html))


def extract_title_and_url(cell_html: str) -> tuple[str, str | None]:
    title = strip_tags(cell_html)
    match = re.search(r"<a[^>]*href=\"([^\"]+)\"", cell_html)
    if not match:
        return title, None
    return title, urljoin("https://en.wikipedia.org", unescape(match.group(1)))


def parse_rows(table_html: str, section: str) -> list[dict]:
    results: list[dict] = []
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", table_html, flags=re.S)

    for row_html in rows[1:]:
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row_html, flags=re.S)
        if len(cells) < 6:
            continue

        title, title_url = extract_title_and_url(cells[1])
        result = {
            "section": section,
            "release_date": normalize_release_date(strip_tags(cells[0])),
            "title": title,
            "title_wikipedia_url": title_url,
            "director": split_list(strip_tags(cells[2])),
            "cast": split_list(strip_tags(cells[3])),
            "studios": split_list(strip_tags(cells[4])),
            "reference_labels": extract_reference_labels(cells[5]),
        }
        results.append(result)

    return results


def extract_films(html: str) -> list[dict]:
    data: list[dict] = []
    heading_pattern = re.compile(
        r"<h3[^>]*>\s*<span[^>]*class=\"mw-headline\"[^>]*>(.*?)</span>\s*</h3>",
        re.S,
    )

    matches = list(heading_pattern.finditer(html))
    for idx, match in enumerate(matches):
        section_name = strip_tags(match.group(1))
        if "–" not in section_name and "-" not in section_name:
            continue

        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(html)
        section_html = html[start:end]

        table_match = re.search(r"<table[^>]*class=\"[^\"]*wikitable[^\"]*\"[^>]*>(.*?)</table>", section_html, flags=re.S)
        if not table_match:
            continue

        data.extend(parse_rows(table_match.group(0), section_name))

    return data


def main() -> None:
    html = fetch_html(SOURCE_URL)
    films = extract_films(html)
    OUTPUT_PATH.write_text(json.dumps(films, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved {len(films)} records to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
