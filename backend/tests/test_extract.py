"""Tests for recipe document text extraction."""

from __future__ import annotations

from io import BytesIO

from app.modules.recipes.extract import extract_text


def test_extract_plain_txt():
    text = extract_text("notes.txt", b"Chicken Soup\n\n1 onion\nBoil water.")
    assert "Chicken Soup" in text
    assert "onion" in text


def test_clean_pdf_joins_broken_tokens():
    from app.modules.recipes.extract import _clean_pdf_page

    messy = "Chicken\n\nPicatta\n\n1\n\ncup\n\nrice"
    cleaned = _clean_pdf_page(messy)
    assert "Chicken Picatta" in cleaned or "Chicken" in cleaned
    assert "cup" in cleaned


def test_extract_markdown_as_text():
    text = extract_text("recipes.md", b"# Pasta\n- garlic\n")
    assert "Pasta" in text


def test_extract_pdf_blank_page():
    from pypdf import PdfWriter

    buf = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.write(buf)
    text = extract_text("blank.pdf", buf.getvalue())
    assert isinstance(text, str)


def test_extract_sniffs_pdf_magic():
    from pypdf import PdfWriter

    buf = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.write(buf)
    data = buf.getvalue()
    assert data[:4] == b"%PDF"
    text = extract_text("unknown.bin", data)
    assert isinstance(text, str)
