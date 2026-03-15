#!/usr/bin/env python3
"""Fetch CNN's current homepage headlines with a small agent wrapper."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


CNN_URL = "https://www.cnn.com"
USER_AGENT = "Mozilla/5.0 (compatible; CNNHeadlineAgent/1.0)"


class HeadlineHTMLParser(HTMLParser):
    """Collect visible text from h1 tags as a fallback headline source."""

    def __init__(self) -> None:
        super().__init__()
        self._in_h1 = False
        self._parts: list[str] = []
        self.headlines: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "h1":
            self._in_h1 = True
            self._parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "h1" and self._in_h1:
            text = _clean_text(" ".join(self._parts))
            if text:
                self.headlines.append(text)
            self._in_h1 = False
            self._parts = []

    def handle_data(self, data: str) -> None:
        if self._in_h1:
            self._parts.append(data)


class ArticleLinkParser(HTMLParser):
    """Collect anchor text for article-style CNN links."""

    def __init__(self) -> None:
        super().__init__()
        self._href: str | None = None
        self._parts: list[str] = []
        self.candidates: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return

        attr_map = dict(attrs)
        href = attr_map.get("href")
        if href:
            self._href = href
            self._parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or not self._href:
            return

        text = _clean_text(" ".join(self._parts))
        if text:
            self.candidates.append((self._href, text))

        self._href = None
        self._parts = []

    def handle_data(self, data: str) -> None:
        if self._href:
            self._parts.append(data)


def _clean_text(value: str) -> str:
    value = unescape(value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _normalize_candidate(value: str) -> str:
    value = _clean_text(value)
    value = re.sub(r"^(?:[•]\s*)+", "", value)
    value = re.sub(
        r"^(?:For Subscribers|Analysis|Video|CNN Exclusive|Exclusive)\s+",
        "",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(r"\s+\d+:\d{2}$", "", value)
    return value.strip()


def _looks_like_story_headline(value: str) -> bool:
    normalized = _normalize_candidate(value)
    word_count = len(normalized.split())

    if len(normalized) < 45 or word_count < 8:
        return False

    lowered = normalized.lower()
    generic_titles = {
        "breaking news, latest news and videos | cnn",
        "domestic desktop homepage",
    }
    if lowered in generic_titles:
        return False

    blocked_terms = {
        "trending",
        "watch live",
        "live tv",
        "cnn",
    }
    if lowered in blocked_terms:
        return False

    if any(token in lowered for token in ("getty images", "bloomberg", "/afp", "show all")):
        return False

    return any(ch.isalpha() for ch in normalized) and " | " not in normalized


def _extract_json_ld_headlines(html: str) -> list[str]:
    matches = re.findall(
        r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>',
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )

    headlines: list[str] = []
    for match in matches:
        raw_json = match.strip()
        if not raw_json:
            continue

        try:
            payload = json.loads(raw_json)
        except json.JSONDecodeError:
            continue

        headlines.extend(_walk_for_headlines(payload))

    return headlines


def _walk_for_headlines(node: object) -> Iterable[str]:
    if isinstance(node, dict):
        headline = node.get("headline")
        if isinstance(headline, str):
            cleaned = _clean_text(headline)
            if cleaned:
                yield cleaned
        for value in node.values():
            yield from _walk_for_headlines(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk_for_headlines(item)


@dataclass
class CNNHeadlineAgent:
    url: str = CNN_URL

    def fetch_homepage(self) -> str:
        request = Request(self.url, headers={"User-Agent": USER_AGENT})
        with urlopen(request, timeout=15) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="replace")

    def extract_headlines(self, html: str, limit: int = 5) -> list[str]:
        headlines: list[str] = []
        seen: set[str] = set()

        def add_candidate(candidate: str) -> None:
            normalized = _normalize_candidate(candidate)
            if normalized and normalized not in seen and _looks_like_story_headline(normalized):
                seen.add(normalized)
                headlines.append(normalized)

        article_link_parser = ArticleLinkParser()
        article_link_parser.feed(html)
        for href, text in article_link_parser.candidates:
            if re.match(r"^/\d{4}/\d{2}/\d{2}/", href):
                add_candidate(text)
                if len(headlines) >= limit:
                    return headlines

        json_ld_headlines = _extract_json_ld_headlines(html)
        for candidate in json_ld_headlines:
            add_candidate(candidate)
            if len(headlines) >= limit:
                return headlines

        parser = HeadlineHTMLParser()
        parser.feed(html)
        for candidate in parser.headlines:
            add_candidate(candidate)
            if len(headlines) >= limit:
                return headlines

        meta_match = re.search(
            r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"',
            html,
            flags=re.IGNORECASE,
        )
        if meta_match:
            add_candidate(meta_match.group(1))
            if len(headlines) >= limit:
                return headlines

        if headlines:
            return headlines[:limit]

        raise ValueError("Could not find headlines on the CNN homepage.")

    def run(self, limit: int = 5) -> list[str]:
        html = self.fetch_homepage()
        return self.extract_headlines(html, limit=limit)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch CNN's current homepage headline."
    )
    parser.add_argument(
        "--url",
        default=CNN_URL,
        help="Homepage URL to fetch. Defaults to CNN.",
    )
    parser.add_argument(
        "--html-file",
        type=Path,
        help="Read HTML from a local file instead of fetching over the network.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print a JSON object with the extracted headlines.",
    )
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args()
    agent = CNNHeadlineAgent(url=args.url)
    try:
        if args.html_file:
            html = args.html_file.read_text(encoding="utf-8")
            headlines = agent.extract_headlines(html, limit=5)
        else:
            headlines = agent.run(limit=5)
    except (
        HTTPError,
        OSError,
        URLError,
        TimeoutError,
        UnicodeDecodeError,
        ValueError,
    ) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps({"headlines": headlines}))
    else:
        print("\n".join(headlines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
