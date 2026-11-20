"""RAG chatbot service stubs.

Next sprint pipeline (do not implement yet):
  upload recipes → store (recipes module) → embed → retrieve → chat

Keep retrieval and chat logic in this module so calendar/shop/budget stay separate.
"""

from __future__ import annotations

from typing import Protocol


class Embedder(Protocol):
    """TODO: embed recipe chunks for vector search."""

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class Retriever(Protocol):
    """TODO: similarity search over indexed recipes."""

    def search(self, query: str, k: int = 5) -> list[str]: ...


class RagChat(Protocol):
    """TODO: answer natural-language meal questions with retrieved recipes."""

    def ask(self, message: str) -> str: ...


class RagPipelineStub:
    """Clear entry point for the next sprint — methods intentionally unimplemented."""

    def index_recipe(self, recipe_id: str, text: str) -> None:
        # TODO: chunk → embed → upsert into vector store
        raise NotImplementedError("TODO: index recipe for RAG retrieval")

    def ask(self, message: str) -> str:
        # TODO: retrieve relevant chunks → LLM answer
        raise NotImplementedError("TODO: RAG chat over user recipes")
