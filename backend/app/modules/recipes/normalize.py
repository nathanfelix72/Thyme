"""Segment via titles/hints; slice raw_text in Python. Prefer zero/few LLM calls."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Callable

from pydantic import BaseModel

from app.modules.recipes.schemas import (
    Ingredient,
    RecipeLocator,
    RecipeMetadata,
    RecipeSegment,
    WebRecipeClean,
)
from app.modules.settings.schemas import LlmTask
from app.modules.settings.store import UserSettings, get_store
from app.modules.shared.llm import build_chat_model

logger = logging.getLogger(__name__)
_STRUCTURED_MAX_RETRIES = 3

ProgressFn = Callable[[dict[str, Any]], None] | None

_PAGE_NOISE = re.compile(r"\n*--- page \d+ ---\n*", re.IGNORECASE)
_TIME_RE = re.compile(
    r"(?P<n>\d+)\s*(?:-\s*\d+\s*)?(?P<u>minutes?|mins?|hours?|hrs?)",
    re.IGNORECASE,
)
_SERVINGS_RE = re.compile(
    r"(?:serves?|servings?|yield)\s*[:\-]?\s*(?P<n>\d+)",
    re.IGNORECASE,
)

# Compact common food tokens for keyword tags (filters also match raw_text).
_FOOD_WORDS = {
    "chicken",
    "beef",
    "pork",
    "lamb",
    "turkey",
    "fish",
    "salmon",
    "shrimp",
    "tofu",
    "egg",
    "eggs",
    "milk",
    "butter",
    "cream",
    "cheese",
    "cheddar",
    "parmesan",
    "mozzarella",
    "garlic",
    "onion",
    "shallot",
    "tomato",
    "tomatoes",
    "potato",
    "potatoes",
    "rice",
    "pasta",
    "noodle",
    "noodles",
    "macaroni",
    "flour",
    "sugar",
    "salt",
    "pepper",
    "lemon",
    "lime",
    "orange",
    "wine",
    "stock",
    "broth",
    "oil",
    "olive",
    "soy",
    "ginger",
    "basil",
    "parsley",
    "cilantro",
    "thyme",
    "rosemary",
    "capers",
    "mushroom",
    "mushrooms",
    "spinach",
    "carrot",
    "carrots",
    "celery",
    "bean",
    "beans",
    "lentil",
    "lentils",
    "bacon",
    "sausage",
    "bread",
    "cream cheese",
}

SEGMENT_SYSTEM = """You list distinct cooking recipes in a document.
Return ONLY valid JSON:
{"recipes":[{"title":"dish name","start_hint":"exact short phrase where it begins"}]}
Rules:
- Titles + short start_hint only. Do NOT copy recipe bodies. Do NOT rewrite.
- start_hint must appear verbatim in the document (usually the title).
- JSON only.
"""

WEB_CLEAN_SYSTEM = """You extract ONE cooking recipe from noisy webpage text.
Match this schema exactly:
title, ingredients[{name, quantity, unit}], steps[], difficulty (easy|medium|hard),
total_time_minutes, servings, cuisine, ingredient_keywords[].
Rules:
- IGNORE ads, nav, comments, ratings, related posts, social widgets, equipment-only lists, nutrition tables, and other non-recipe fluff.
- Keep ONLY the real ingredient list and cooking instructions for this dish.
- ALWAYS fill difficulty, total_time_minutes, servings, cuisine (estimate medium / 30 / 4 / general if missing).
- If the page is not actually a recipe, return empty ingredients and steps.
"""

_DEFAULT_DIFFICULTY = "medium"
_DEFAULT_TIME_MINUTES = 30
_DEFAULT_SERVINGS = 4
_DEFAULT_CUISINE = "general"
_WEB_CLEAN_CHARS = 10000


def _strip_json_fence(text: str) -> str:
    text = text.strip()
    fence = re.match(r"^```(?:json)?\s*([\s\S]*?)\s*```$", text, re.IGNORECASE)
    if fence:
        return fence.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start : end + 1]
    return text


def _user_model(user_id: str, *, task: LlmTask | None = None) -> Any:
    settings: UserSettings = get_store().get(user_id)
    return build_chat_model(
        settings.provider_for(task),
        openai_api_key=settings.openai_api_key,
        anthropic_api_key=settings.anthropic_api_key,
        ollama_model=settings.ollama_model,
    )


def _invoke_json(
    user_id: str,
    prompt: str,
    *,
    task: LlmTask | None = None,
) -> dict[str, Any]:
    model = _user_model(user_id, task=task)
    result = model.invoke(prompt)
    raw = getattr(result, "content", None) or str(result)
    if isinstance(raw, list):
        raw = "".join(
            part.get("text", "") if isinstance(part, dict) else str(part) for part in raw
        )
    payload = json.loads(_strip_json_fence(str(raw)))
    if not isinstance(payload, dict):
        raise ValueError("LLM did not return a JSON object")
    return payload


def _invoke_structured(
    user_id: str,
    prompt: str,
    schema: type[BaseModel],
    *,
    task: LlmTask | None = None,
    max_retries: int = _STRUCTURED_MAX_RETRIES,
) -> BaseModel:
    """Lab3-style structured output with bounded retries, then JSON fallback."""
    model = _user_model(user_id, task=task)
    last_error: Exception | None = None
    try:
        structured = model.with_structured_output(schema)
    except Exception as exc:
        logger.warning("with_structured_output unavailable (%s); using JSON fallback", exc)
        structured = None

    if structured is not None:
        for attempt in range(1, max_retries + 1):
            try:
                result = structured.invoke(prompt)
                if result is None:
                    raise ValueError("empty structured result")
                if isinstance(result, schema):
                    return result
                return schema.model_validate(result)
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "structured invoke attempt %s/%s failed: %s",
                    attempt,
                    max_retries,
                    exc,
                )

    try:
        payload = _invoke_json(user_id, prompt, task=task)
        return schema.model_validate(payload)
    except Exception as exc:
        raise last_error or exc


def strip_page_noise(text: str) -> str:
    return _PAGE_NOISE.sub("\n\n", text).strip()


def _find_hint(haystack: str, hint: str, *, from_index: int = 0) -> int:
    if not hint:
        return -1
    idx = haystack.find(hint, from_index)
    if idx >= 0:
        return idx
    return haystack.lower().find(hint.lower(), from_index)


def _title_from_start(chunk: str) -> str:
    line = chunk.strip().split("\n", 1)[0].strip()
    # Truncate long first lines (title glued to ingredients)
    if len(line) > 60:
        # Prefer cut before first digit quantity
        m = re.search(r"\s+\d", line)
        if m and m.start() >= 8:
            line = line[: m.start()].strip()
        else:
            line = line[:60].rstrip()
    return line or "Recipe"


def _looks_like_title_line(line: str) -> bool:
    s = line.strip()
    if not s or len(s) < 3 or len(s) > 70:
        return False
    low = s.lower()
    if low.startswith(
        ("ingredients", "directions", "instructions", "steps", "method", "notes")
    ):
        return False
    if re.match(r"^[\d\W]+$", s):
        return False
    # Numbered step
    if re.match(r"^\d+[\.\)]\s", s):
        return False
    # Quantity-led ingredient line
    if re.match(r"^[\d½¼¾⅓⅔]+\s", s):
        return False
    # Instruction-ish (not a dish title)
    if re.search(r"\b(minutes?|hours?|degrees?|oven|preheat|simmer|whisk|stir)\b", low):
        return False
    if s.endswith("."):
        return False
    letters = sum(ch.isalpha() for ch in s)
    if letters < 3:
        return False
    if s.count(".") > 0:
        return False
    words = s.split()
    if len(words) > 8:
        return False
    return True


def heuristic_segments(text: str) -> list[RecipeSegment]:
    """
    Fast, format-tolerant split: blank-line blocks and title-like lines.
    No LLM. Slices are always verbatim from `text`.
    """
    cleaned = text.strip()
    if not cleaned:
        return []

    starts: list[tuple[int, str]] = []
    # Prefer blank-line separated blocks whose first line looks like a title
    for m in re.finditer(r"(?:^|\n\n+)([^\n]{3,70})(?=\n|$)", cleaned):
        line = m.group(1).strip()
        if _looks_like_title_line(line):
            starts.append((m.start(1), line))

    # Also catch title glued to body on same line (Felix-style)
    for m in re.finditer(
        r"(?:^|\n)([A-Z][A-Za-z][A-Za-z0-9'&/\- ]{2,40})(?=\s+\d)",
        cleaned,
    ):
        title = m.group(1).strip()
        if _looks_like_title_line(title) or len(title.split()) <= 6:
            starts.append((m.start(1), title))

    if not starts:
        return [RecipeSegment(title=_title_from_start(cleaned), raw_text=cleaned)]

    starts.sort(key=lambda x: x[0])
    deduped: list[tuple[int, str]] = []
    for pos, title in starts:
        if deduped and abs(pos - deduped[-1][0]) < 30:
            continue
        # Skip if this "title" is inside previous body too soon and looks weak
        deduped.append((pos, title))

    # Collapse same title to earliest
    earliest: dict[str, tuple[int, str]] = {}
    for pos, title in deduped:
        key = re.sub(r"\s+", " ", title.lower()).strip()
        if key not in earliest or pos < earliest[key][0]:
            earliest[key] = (pos, title)
    boundary = sorted(earliest.values(), key=lambda x: x[0])

    # If we only found one start near the beginning, keep whole doc as one
    # unless there are clear later starts
    out: list[RecipeSegment] = []
    for i, (start, title) in enumerate(boundary):
        end = boundary[i + 1][0] if i + 1 < len(boundary) else len(cleaned)
        raw = cleaned[start:end].strip()
        # Drop tiny junk slices
        if len(raw) < 40 and i > 0:
            continue
        out.append(RecipeSegment(title=title or _title_from_start(raw), raw_text=raw))

    return out or [RecipeSegment(title=_title_from_start(cleaned), raw_text=cleaned)]


def slice_segments_from_locators(
    document: str,
    locators: list[RecipeLocator],
    *,
    base_offset: int = 0,
) -> list[tuple[int, RecipeSegment]]:
    positions: list[tuple[int, str]] = []
    cursor = 0
    for loc in locators:
        title = (loc.title or "").strip() or "Recipe"
        hint = (loc.start_hint or title).strip()
        idx = _find_hint(document, hint, from_index=cursor)
        if idx < 0:
            idx = _find_hint(document, title, from_index=0)
        if idx < 0:
            continue
        positions.append((base_offset + idx, title))
        cursor = idx + 1

    if not positions:
        return []

    positions.sort(key=lambda p: p[0])
    deduped: list[tuple[int, str]] = []
    for pos, title in positions:
        if deduped and abs(pos - deduped[-1][0]) < 40:
            continue
        deduped.append((pos, title))

    out: list[tuple[int, RecipeSegment]] = []
    for i, (abs_start, title) in enumerate(deduped):
        local_start = abs_start - base_offset
        local_end = (
            deduped[i + 1][0] - base_offset
            if i + 1 < len(deduped)
            else len(document)
        )
        raw = document[local_start:local_end].strip()
        if raw:
            out.append((abs_start, RecipeSegment(title=title, raw_text=raw)))
    return out


def _llm_segment_once(
    user_id: str,
    cleaned: str,
    *,
    hint: str | None,
    on_progress: ProgressFn,
) -> list[RecipeSegment]:
    """Single LLM call on a skeleton (line samples), then slice full text."""
    # Build a compact skeleton so the prompt stays small
    lines = [ln.strip() for ln in cleaned.splitlines() if ln.strip()]
    skeleton_lines: list[str] = []
    for i, ln in enumerate(lines):
        if i < 3 or _looks_like_title_line(ln) or (i % 8 == 0 and len(ln) < 80):
            skeleton_lines.append(ln[:100])
        if len(skeleton_lines) >= 80:
            break
    skeleton = "\n".join(skeleton_lines)[:6000]
    if on_progress:
        on_progress(
            {
                "stage": "segment",
                "message": "One LLM pass for recipe titles (skeleton)…",
                "percent": 25,
                "prompt_preview": SEGMENT_SYSTEM[:200] + "…",
            }
        )
    prompt = (
        f"{SEGMENT_SYSTEM}\n\n"
        f"Document hint: {hint or 'unknown'}\n"
        f"Skeleton lines from the document (not the full text):\n\n{skeleton}"
    )
    payload = _invoke_json(user_id, prompt, task="segment")
    locators: list[RecipeLocator] = []
    for item in payload.get("recipes") or []:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        start_hint = str(item.get("start_hint") or title).strip()
        if not title and not start_hint:
            continue
        locators.append(
            RecipeLocator(title=title or start_hint[:60], start_hint=start_hint)
        )
    pairs = slice_segments_from_locators(cleaned, locators, base_offset=0)
    if not pairs:
        return []
    # Re-slice by absolute starts across full doc
    starts = [(p, s.title) for p, s in pairs]
    earliest: dict[str, tuple[int, str]] = {}
    for pos, title in starts:
        key = re.sub(r"\s+", " ", title.lower()).strip()
        if key not in earliest or pos < earliest[key][0]:
            earliest[key] = (pos, title)
    boundary = sorted(earliest.values(), key=lambda x: x[0])
    out: list[RecipeSegment] = []
    for i, (start, title) in enumerate(boundary):
        end = boundary[i + 1][0] if i + 1 < len(boundary) else len(cleaned)
        raw = cleaned[start:end].strip()
        if raw:
            out.append(RecipeSegment(title=title, raw_text=raw))
    return out


def segment_document(
    user_id: str,
    text: str,
    *,
    hint: str | None = None,
    on_progress: ProgressFn = None,
) -> list[RecipeSegment]:
    """Prefer heuristic split (0 LLM). Fall back to one tiny title-list LLM call."""
    cleaned = strip_page_noise(text)
    if not cleaned:
        return []

    def progress(event: dict[str, Any]) -> None:
        if on_progress:
            on_progress(event)

    progress(
        {
            "stage": "segment",
            "message": "Heuristic segment (no LLM)…",
            "percent": 18,
        }
    )
    unique = heuristic_segments(cleaned)

    # If heuristic found only one blob but doc is large, try one LLM title pass
    if len(unique) <= 1 and len(cleaned) > 2500:
        try:
            llm_segs = _llm_segment_once(
                user_id, cleaned, hint=hint, on_progress=progress
            )
            if len(llm_segs) > len(unique):
                unique = llm_segs
        except Exception as exc:
            logger.warning("LLM segment fallback failed: %s", exc)
            progress(
                {
                    "stage": "segment",
                    "message": f"LLM segment skipped ({exc}); using heuristic",
                    "percent": 50,
                }
            )

    progress(
        {
            "stage": "segment",
            "message": f"Found {len(unique)} recipe segment(s): "
            + (", ".join(s.title for s in unique[:8]) or "none")
            + ("…" if len(unique) > 8 else ""),
            "found": len(unique),
            "titles": [s.title for s in unique],
            "percent": 55,
        }
    )
    return unique


def enrich_metadata(
    user_id: str,
    segment: RecipeSegment,
    *,
    on_progress: ProgressFn = None,
) -> RecipeMetadata:
    """Rule-based metadata only — no LLM (filters already use raw_text)."""
    _ = user_id  # kept for call-site compatibility
    meta = metadata_from_rules(segment)
    if on_progress:
        on_progress(
            {
                "stage": "metadata",
                "message": (
                    f"“{segment.title}”: difficulty={meta.difficulty}, "
                    f"time={meta.total_time_minutes}, "
                    f"keywords={', '.join(meta.ingredient_keywords[:6]) or '—'}"
                ),
            }
        )
    return meta


def metadata_from_rules(segment: RecipeSegment) -> RecipeMetadata:
    text = segment.raw_text or ""
    lower = text.lower()

    total_time: int | None = None
    for m in _TIME_RE.finditer(text):
        n = int(m.group("n"))
        unit = m.group("u").lower()
        minutes = n * 60 if unit.startswith("h") else n
        total_time = minutes if total_time is None else max(total_time, minutes)

    servings = None
    sm = _SERVINGS_RE.search(text)
    if sm:
        servings = int(sm.group("n"))

    difficulty = None
    if re.search(r"\b(easy|simple|quick)\b", lower):
        difficulty = "easy"
    elif re.search(r"\b(hard|advanced|challenging)\b", lower):
        difficulty = "hard"
    elif re.search(r"\bmedium\b", lower):
        difficulty = "medium"

    cuisine = None
    for name in (
        "italian",
        "mexican",
        "chinese",
        "japanese",
        "thai",
        "indian",
        "french",
        "greek",
        "korean",
        "american",
    ):
        if re.search(rf"\b{name}\b", lower):
            cuisine = name
            break

    keywords: list[str] = []
    for food in sorted(_FOOD_WORDS, key=len, reverse=True):
        if food in lower and food not in keywords:
            keywords.append(food)
        if len(keywords) >= 12:
            break

    return RecipeMetadata(
        difficulty=difficulty,  # type: ignore[arg-type]
        total_time_minutes=total_time,
        servings=servings,
        cuisine=cuisine,
        ingredient_keywords=keywords,
        tags=[],
    )


def normalize_document(
    user_id: str,
    text: str,
    *,
    hint: str | None = None,
    on_progress: ProgressFn = None,
) -> list[tuple[RecipeSegment, RecipeMetadata]]:
    """Locate recipes → slice verbatim → rule metadata (LLM only if needed)."""
    segments = segment_document(
        user_id, text, hint=hint, on_progress=on_progress
    )
    if not segments:
        cleaned = strip_page_noise(text)
        if not cleaned:
            return []
        segments = [
            RecipeSegment(
                title=(hint or "Uploaded recipe").rsplit(".", 1)[0][:80],
                raw_text=cleaned,
            )
        ]

    out: list[tuple[RecipeSegment, RecipeMetadata]] = []
    for i, seg in enumerate(segments, start=1):
        if on_progress:
            on_progress(
                {
                    "stage": "metadata",
                    "current": i,
                    "total": len(segments),
                    "percent": 55 + int(35 * i / max(len(segments), 1)),
                    "message": f"Metadata {i}/{len(segments)}: {seg.title}",
                }
            )
        meta = enrich_metadata(user_id, seg, on_progress=on_progress)
        out.append((seg, meta))
    return out


def _coerce_web_ingredients(raw: Any) -> list[Ingredient]:
    if not isinstance(raw, list):
        return []
    out: list[Ingredient] = []
    for item in raw:
        if isinstance(item, str):
            name = item.strip()
            if name:
                out.append(Ingredient(name=name[:120]))
            continue
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("ingredient") or "").strip()
        if not name:
            continue
        qty = item.get("quantity")
        unit = item.get("unit")
        out.append(
            Ingredient(
                name=name[:120],
                quantity=str(qty).strip()[:40] if qty not in (None, "") else None,
                unit=str(unit).strip()[:40] if unit not in (None, "") else None,
            )
        )
    return out[:40]


def _coerce_web_steps(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    steps: list[str] = []
    for item in raw:
        if isinstance(item, str):
            text = item.strip()
        elif isinstance(item, dict):
            text = str(item.get("text") or item.get("step") or "").strip()
        else:
            continue
        if text:
            steps.append(text[:800])
    return steps[:30]


def _format_clean_raw_text(
    title: str,
    ingredients: list[Ingredient],
    steps: list[str],
    *,
    source_url: str | None = None,
) -> str:
    lines = [title.strip() or "Web recipe", ""]
    if ingredients:
        lines.append("Ingredients")
        for ing in ingredients:
            line = " ".join(
                p for p in [ing.quantity, ing.unit, ing.name] if p
            ).strip()
            lines.append(f"- {line}")
        lines.append("")
    if steps:
        lines.append("Instructions")
        for i, step in enumerate(steps, start=1):
            lines.append(f"{i}. {step}")
        lines.append("")
    if source_url:
        lines.append(f"Source: {source_url}")
    return "\n".join(lines).strip()


def clean_web_snippet(
    user_id: str,
    *,
    title: str,
    content: str,
    source_url: str | None = None,
    on_progress: ProgressFn = None,
) -> tuple[RecipeSegment, RecipeMetadata] | None:
    """LLM-clean noisy webpage text → ingredients + instructions only."""
    excerpt = content.strip()[:_WEB_CLEAN_CHARS]
    if not excerpt:
        return None
    if on_progress:
        on_progress(
            {
                "stage": "web_clean",
                "message": f"Cleaning web recipe “{title}”…",
                "prompt_preview": WEB_CLEAN_SYSTEM[:200] + "…",
                "url": source_url,
            }
        )
    prompt = (
        f"{WEB_CLEAN_SYSTEM}\n\n"
        f"Page title: {title}\n"
        f"URL: {source_url or 'unknown'}\n\n"
        f"Page text:\n{excerpt}"
    )
    try:
        cleaned = _invoke_structured(
            user_id, prompt, WebRecipeClean, task="web_clean"
        )
        assert isinstance(cleaned, WebRecipeClean)
    except Exception as exc:
        logger.warning("web clean failed for %s: %s", title, exc)
        if on_progress:
            on_progress(
                {
                    "stage": "web_clean",
                    "message": f"Clean failed for “{title}” — skipped ({exc})",
                    "rejected": True,
                }
            )
        return None

    cleaned_title = (cleaned.title or title).strip()[:120] or title
    ingredients = _coerce_web_ingredients(
        [ing.model_dump() for ing in cleaned.ingredients]
    )
    steps = _coerce_web_steps(cleaned.steps)
    if not ingredients and not steps:
        if on_progress:
            on_progress(
                {
                    "stage": "web_clean",
                    "message": f"“{cleaned_title}” had no extractable recipe — skipped",
                    "rejected": True,
                }
            )
        return None

    diff = cleaned.difficulty if cleaned.difficulty in ("easy", "medium", "hard") else _DEFAULT_DIFFICULTY
    t = cleaned.total_time_minutes
    if not isinstance(t, (int, float)) or int(t) <= 0:
        t = _DEFAULT_TIME_MINUTES
    s = cleaned.servings
    if not isinstance(s, (int, float)) or int(s) <= 0:
        s = _DEFAULT_SERVINGS
    cuisine = (cleaned.cuisine or "").strip()[:60] or _DEFAULT_CUISINE
    keywords = [
        str(k).strip().lower()[:60]
        for k in (cleaned.ingredient_keywords or [])
        if str(k).strip()
    ][:20]
    if not keywords and ingredients:
        keywords = [ing.name.lower() for ing in ingredients[:12]]

    raw_text = _format_clean_raw_text(
        cleaned_title, ingredients, steps, source_url=source_url
    )
    seg = RecipeSegment(title=cleaned_title, raw_text=raw_text)
    meta = RecipeMetadata(
        difficulty=diff,  # type: ignore[arg-type]
        total_time_minutes=int(t),
        servings=int(s),
        cuisine=cuisine,
        ingredient_keywords=keywords,
        tags=[],
        ingredients=ingredients,
        steps=steps,
    )
    if on_progress:
        on_progress(
            {
                "stage": "web_clean",
                "message": (
                    f"Cleaned “{cleaned_title}”: "
                    f"{len(ingredients)} ingredients, {len(steps)} steps"
                ),
            }
        )
    return seg, meta


def recipes_from_web_snippets(
    user_id: str,
    snippets: list[dict[str, str]],
    *,
    on_progress: ProgressFn = None,
) -> list[tuple[RecipeSegment, RecipeMetadata, str | None]]:
    """Web hits → LLM-cleaned ingredients/instructions + metadata."""
    results: list[tuple[RecipeSegment, RecipeMetadata, str | None]] = []
    for i, snip in enumerate(snippets[:6], start=1):
        title = (snip.get("title") or f"Web recipe {i}").strip()
        url = snip.get("url") or None
        content = (snip.get("content") or snip.get("raw_content") or "").strip()
        if not content:
            continue
        cleaned = clean_web_snippet(
            user_id,
            title=title,
            content=content,
            source_url=url,
            on_progress=on_progress,
        )
        if not cleaned:
            continue
        seg, meta = cleaned
        results.append((seg, meta, url))
    return results
