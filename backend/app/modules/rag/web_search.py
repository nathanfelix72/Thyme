"""Single non-agentic web search call (Tavily)."""

from __future__ import annotations

from app.modules.shared import config


def build_web_query(
    *,
    query: str | None,
    include_ingredients: list[str] | None,
    exclude_ingredients: list[str] | None,
    max_time_minutes: int | None,
    difficulty: str | None,
    cuisine: str | None,
) -> str:
    """Build a Tavily query that emphasizes required ingredients together."""
    parts: list[str] = ["recipe"]
    if query and query.strip():
        parts.append(query.strip())
    includes = [i.strip() for i in (include_ingredients or []) if i and i.strip()]
    if includes:
        parts.append("with " + " and ".join(includes))
    if cuisine:
        parts.append(cuisine)
    if difficulty:
        parts.append(f"{difficulty} difficulty")
    if max_time_minutes is not None:
        parts.append(f"under {max_time_minutes} minutes")
    if exclude_ingredients:
        for item in exclude_ingredients:
            cleaned = item.strip()
            if cleaned:
                parts.append(f"-{cleaned}")
                parts.append(f"without {cleaned}")
    return " ".join(parts)


def tavily_search(
    query: str,
    *,
    max_results: int = 8,
    api_key: str | None = None,
) -> list[dict[str, str]]:
    """Exactly one Tavily search. Returns [{title, url, content}, ...].

    Prefer the caller's per-user key; fall back to process env for local/dev only.
    """
    key = (api_key or config.TAVILY_API_KEY or "").strip()
    if not key:
        raise ValueError(
            "No Tavily API key. Add yours under AI settings (per account)."
        )

    from tavily import TavilyClient

    client = TavilyClient(api_key=key)
    # Prefer fuller page text when available so ingredients/steps can be extracted.
    try:
        resp = client.search(
            query=query,
            max_results=max_results,
            search_depth="advanced",
            include_answer=False,
            include_raw_content=True,
        )
    except TypeError:
        resp = client.search(
            query=query,
            max_results=max_results,
            search_depth="basic",
            include_answer=False,
        )
    results = resp.get("results") if isinstance(resp, dict) else None
    if not results:
        return []

    out: list[dict[str, str]] = []
    for item in results:
        content = str(
            item.get("raw_content")
            or item.get("content")
            or item.get("snippet")
            or ""
        ).strip()
        # Cap extremely long pages for LLM metadata calls
        if len(content) > 12000:
            content = content[:12000]
        out.append(
            {
                "title": str(item.get("title") or ""),
                "url": str(item.get("url") or ""),
                "content": content,
            }
        )
    return out
