"""Fetch a recipe web page and turn it into text for extraction.

Strategy:
1. Most recipe sites embed schema.org Recipe JSON-LD for Google rich results.
   If present, it's clean structured data with none of the life-story/ads noise,
   so we flatten that to text.
2. Otherwise fall back to the page's visible text (scripts/nav/footer removed).

Either way the text still goes through the LLM so output matches our schema.

Safety: this fetches user-supplied URLs from our server, so we block requests
to private/loopback/link-local addresses (SSRF -- e.g. the AWS metadata
endpoint 169.254.169.254) and re-check every redirect hop.
"""

from __future__ import annotations

import ipaddress
import json
import re
import socket
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

MAX_PAGE_BYTES = 5 * 1024 * 1024
MAX_REDIRECTS = 5
TIMEOUT_SECONDS = 15
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36 ThymeRecipeImporter/0.1"
)


class UrlFetchError(ValueError):
    pass


# ---------------------------------------------------------------- fetching

def _check_public_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise UrlFetchError("URL must start with http:// or https://")
    try:
        infos = socket.getaddrinfo(parsed.hostname, parsed.port or None)
    except socket.gaierror as exc:
        raise UrlFetchError(f"Couldn't resolve host '{parsed.hostname}'.") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise UrlFetchError("That URL points to a private or local address.")


def fetch_html(url: str) -> tuple[str, str]:
    """Return (final_url, html). Follows redirects manually so every hop is checked."""
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"}
    with httpx.Client(timeout=TIMEOUT_SECONDS, follow_redirects=False, headers=headers) as client:
        for _ in range(MAX_REDIRECTS + 1):
            _check_public_url(url)
            try:
                with client.stream("GET", url) as resp:
                    if resp.is_redirect:
                        url = urljoin(url, resp.headers.get("location", ""))
                        continue
                    if resp.status_code in (401, 403, 429):
                        raise UrlFetchError(
                            f"The site refused the request (HTTP {resp.status_code}). "
                            "Some sites block automated access; try pasting the recipe text instead."
                        )
                    if resp.status_code >= 400:
                        raise UrlFetchError(f"The site returned HTTP {resp.status_code}.")
                    ctype = resp.headers.get("content-type", "")
                    if "html" not in ctype:
                        raise UrlFetchError(f"Expected a web page but got '{ctype or 'unknown'}'.")
                    body = bytearray()
                    for chunk in resp.iter_bytes():
                        body.extend(chunk)
                        if len(body) > MAX_PAGE_BYTES:
                            raise UrlFetchError("Page is larger than 5 MB.")
                    return url, body.decode(resp.encoding or "utf-8", errors="replace")
            except httpx.HTTPError as exc:
                raise UrlFetchError(f"Couldn't fetch the page: {exc}") from exc
    raise UrlFetchError("Too many redirects.")


# ---------------------------------------------------------------- JSON-LD

def _iter_nodes(data: Any):
    """Yield every dict in a JSON-LD blob (handles lists and @graph)."""
    if isinstance(data, list):
        for item in data:
            yield from _iter_nodes(item)
    elif isinstance(data, dict):
        yield data
        if "@graph" in data:
            yield from _iter_nodes(data["@graph"])


def _is_recipe(node: dict) -> bool:
    t = node.get("@type")
    types = t if isinstance(t, list) else [t]
    return "Recipe" in types


def find_recipe_jsonld(soup: BeautifulSoup) -> dict | None:
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or tag.get_text() or "")
        except (json.JSONDecodeError, TypeError):
            continue
        for node in _iter_nodes(data):
            if _is_recipe(node):
                return node
    return None


def _iso_duration_to_minutes(value: Any) -> int | None:
    """'PT1H30M' -> 90. Returns None if unparseable."""
    if not isinstance(value, str):
        return None
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", value.strip())
    if not m or not any(m.groups()):
        return None
    d, h, mins, _ = (int(g) if g else 0 for g in m.groups())
    return d * 1440 + h * 60 + mins


def _clean(text: Any) -> str:
    plain = BeautifulSoup(str(text), "html.parser").get_text()
    return re.sub(r"\s+", " ", plain).strip()


def _instructions(value: Any) -> list[str]:
    """Flatten recipeInstructions: string, list of strings, HowToStep, HowToSection."""
    if isinstance(value, str):
        return [_clean(value)]
    steps: list[str] = []
    if isinstance(value, list):
        for item in value:
            steps.extend(_instructions(item))
    elif isinstance(value, dict):
        if "itemListElement" in value:  # HowToSection
            if value.get("name"):
                steps.append(f"[{_clean(value['name'])}]")
            steps.extend(_instructions(value["itemListElement"]))
        elif value.get("text"):
            steps.append(_clean(value["text"]))
    return [s for s in steps if s]


def jsonld_to_text(node: dict) -> str:
    lines: list[str] = [_clean(node.get("name") or "Untitled recipe")]
    if node.get("description"):
        lines.append(_clean(node["description"]))

    yield_ = node.get("recipeYield")
    if isinstance(yield_, list):
        yield_ = yield_[0] if yield_ else None
    if yield_:
        lines.append(f"Servings: {_clean(yield_)}")

    for key, label in (("prepTime", "Prep time"), ("cookTime", "Cook time"), ("totalTime", "Total time")):
        mins = _iso_duration_to_minutes(node.get(key))
        if mins is not None:
            lines.append(f"{label}: {mins} minutes")

    for key, label in (("recipeCuisine", "Cuisine"), ("recipeCategory", "Category"), ("keywords", "Keywords")):
        val = node.get(key)
        if isinstance(val, list):
            val = ", ".join(map(str, val))
        if val:
            lines.append(f"{label}: {_clean(val)}")

    ingredients = node.get("recipeIngredient") or node.get("ingredients") or []
    if ingredients:
        lines.append("\nIngredients:")
        lines.extend(f"- {_clean(i)}" for i in ingredients)

    steps = _instructions(node.get("recipeInstructions"))
    if steps:
        lines.append("\nInstructions:")
        n = 0
        for s in steps:
            if s.startswith("[") and s.endswith("]"):  # section heading, not a step
                lines.append(s)
            else:
                n += 1
                lines.append(f"{n}. {s}")

    return "\n".join(lines)


# ---------------------------------------------------------------- fallback

def visible_text(soup: BeautifulSoup) -> str:
    for tag in soup(["script", "style", "noscript", "svg", "nav", "header", "footer", "aside", "form", "iframe"]):
        tag.decompose()
    root = soup.find("article") or soup.find("main") or soup.body or soup
    text = root.get_text("\n", strip=True)
    return re.sub(r"\n{3,}", "\n\n", text)


def recipe_text_from_url(url: str) -> tuple[str, str, str]:
    """Return (final_url, text, method) where method is 'jsonld' or 'page_text'."""
    final_url, html = fetch_html(url.strip())
    soup = BeautifulSoup(html, "html.parser")

    node = find_recipe_jsonld(soup)
    if node:
        return final_url, jsonld_to_text(node), "jsonld"

    text = visible_text(soup)
    if len(text) < 200:
        raise UrlFetchError(
            "Couldn't find recipe content on that page (it may load content with JavaScript). "
            "Try pasting the recipe text instead."
        )
    return final_url, text, "page_text"
