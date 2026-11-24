"""Recipe Intelligent Document Analysis: raw upload -> text -> validated Recipe.

Pattern reused from lab3 IDA script 2: bind a Pydantic schema with
with_structured_output() and wrap the call in a bounded retry. Unlike the 10-K
lab there's no chunking or keyword prefilter -- a recipe fits in one call, and
splitting it would separate ingredients from steps.
"""

from __future__ import annotations

import io
from typing import Any

from langchain_core.prompts import PromptTemplate
from pypdf import PdfReader

from app.modules.recipes.schemas import Recipe

MAX_RETRIES = 3
MAX_SOURCE_CHARS = 30_000  # guard against huge uploads blowing the context window

EXTRACTION_INSTRUCTIONS = """You are a meticulous recipe editor converting a recipe
document into structured data.

Extract only information present in the text below. Do not invent ingredients,
steps, or times. Null or an empty list is a correct answer when the text doesn't
say something.

title: the recipe's name. If none is given, write a short descriptive name.

servings: the number of servings or portions. If a range is given ("4-6"), use the
lower number. Null if not stated.

ingredients: one entry per ingredient line.
- name: the ingredient itself, no amounts ("all-purpose flour", not "2 cups flour").
- quantity: a number. Convert fractions and mixed numbers (1/2 -> 0.5, 1 1/2 -> 1.5).
  For ranges ("2-3 cloves") use the lower number. "Salt to taste" or "a pinch" -> null.
- unit: cup, tbsp, tsp, g, kg, oz, lb, ml, l, clove, can, etc. Null for countable
  whole items ("3 eggs" -> quantity 3, unit null).
- notes: preparation or state ("diced", "softened", "optional"). Not the unit.
If a recipe has sections ("For the sauce"), still list every ingredient once.

steps: the instructions in order, one action-focused step per item. Remove step
numbers. Don't merge the whole method into one item, and don't include headnotes,
stories, or tips that aren't instructions.

difficulty:
- easy: few ingredients, basic techniques (stirring, boiling, roasting), little
  timing pressure.
- medium: several components or techniques (searing, making a sauce, kneading).
- hard: advanced technique or precision (laminated dough, tempering, emulsions that
  can break, multi-day processes).
Judge from the steps, not from words like "simple" in the title.

prep_time_minutes: hands-on time before cooking (chopping, mixing). Convert hours to
minutes. Null if not stated and not reasonably clear.
cook_time_minutes: time on the heat or in the oven.
total_time_minutes: start to finish, INCLUDING passive time such as marinating,
rising, chilling, or resting. Use the stated total if one is given; otherwise sum
what's known.

tags: 3-8 short lowercase tags covering cuisine ("italian"), meal type ("dinner",
"dessert"), dietary fit ("vegetarian", "gluten-free") ONLY if true from the
ingredients, and main ingredient ("chicken"). No sentences.

Never restate any of this guidance as if it were recipe content.

Recipe text:
{text}
"""

PROMPT = PromptTemplate.from_template(EXTRACTION_INSTRUCTIONS)


class UnsupportedFileError(ValueError):
    pass


def extract_text(filename: str, content_type: str | None, data: bytes) -> str:
    """Turn an uploaded file into plain text. PDFs and text files for now;
    images (OCR / vision) come later."""
    name = (filename or "").lower()
    ctype = (content_type or "").lower()

    if name.endswith(".pdf") or ctype == "application/pdf":
        reader = PdfReader(io.BytesIO(data))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        if not text.strip():
            raise UnsupportedFileError(
                "No text found in this PDF. It may be a scanned image; image upload isn't supported yet."
            )
        return text

    if ctype.startswith("text/") or name.endswith((".txt", ".md")):
        return data.decode("utf-8", errors="replace")

    raise UnsupportedFileError(
        f"Unsupported file type '{content_type or name}'. Upload a PDF or a .txt file."
    )


def extract_recipe(
    text: str,
    chat_model: Any,
    max_retries: int = MAX_RETRIES,
) -> tuple[Recipe, int]:
    """Run structured extraction with a bounded retry.

    Returns (recipe, attempts_used). Raises RuntimeError with the last error
    if every attempt fails validation.
    """
    text = text.strip()[:MAX_SOURCE_CHARS]
    if not text:
        raise ValueError("Recipe text is empty.")

    chain = PROMPT | chat_model.with_structured_output(Recipe)

    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            result = chain.invoke({"text": text})
            if result is None:
                raise ValueError("Model returned no structured output.")
            return result, attempt
        except Exception as exc:  # noqa: BLE001 -- Pydantic ValidationError + provider parse errors
            last_error = exc
    raise RuntimeError(
        f"Recipe extraction failed after {max_retries} attempts: {last_error}"
    ) from last_error
