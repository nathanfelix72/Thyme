"""Extract plain text from uploaded recipe documents."""

from __future__ import annotations

import re
from io import BytesIO


def extract_text(filename: str, data: bytes) -> str:
    """Return plain text from PDF or TXT bytes."""
    name = (filename or "").lower()
    if name.endswith(".pdf"):
        return _extract_pdf(data)
    if name.endswith(".txt") or name.endswith(".md"):
        return data.decode("utf-8", errors="replace")
    # Sniff PDF magic
    if data[:4] == b"%PDF":
        return _extract_pdf(data)
    return data.decode("utf-8", errors="replace")


def _clean_pdf_page(text: str) -> str:
    """Collapse common PDF extraction artifacts (one-token-per-line dumps)."""
    raw_lines = [ln.strip() for ln in text.splitlines()]
    non_empty = [ln for ln in raw_lines if ln]
    if not non_empty:
        return ""

    avg_len = sum(len(ln) for ln in non_empty) / max(len(non_empty), 1)
    # Felix-style PDFs: almost every word on its own line
    if avg_len <= 18:
        joined = " ".join(non_empty)
        # Keep numbered steps on new lines when possible
        joined = re.sub(r"\s+(\d+)\.\s+", r"\n\1. ", joined)
        joined = re.sub(r"[ \t]{2,}", " ", joined)
        return joined.strip()

    cleaned: list[str] = []
    buf: list[str] = []
    for ln in raw_lines:
        if not ln:
            if buf:
                cleaned.append(" ".join(buf))
                buf = []
            cleaned.append("")
            continue
        if len(ln) <= 24 and " " not in ln:
            buf.append(ln)
            continue
        if buf:
            cleaned.append(" ".join(buf))
            buf = []
        cleaned.append(ln)
    if buf:
        cleaned.append(" ".join(buf))
    text = "\n".join(cleaned)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_pdf(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(data))
    pages: list[str] = []
    for i, page in enumerate(reader.pages):
        text = _clean_pdf_page(page.extract_text() or "")
        if text:
            pages.append(f"--- page {i + 1} ---\n{text}")
    return "\n\n".join(pages).strip()
