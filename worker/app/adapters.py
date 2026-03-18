from __future__ import annotations

from dataclasses import dataclass

from .models import Document


@dataclass(slots=True)
class DocumentFragment:
    title: str
    normalized_content: str


class DocumentContentAdapter:
    """Adapter converts persistence model to fragments convenient for generation logic."""

    def adapt(self, documents: list[Document]) -> list[DocumentFragment]:
        return [
            DocumentFragment(
                title=document.title,
                normalized_content=" ".join(document.content.replace("\n", " ").split()),
            )
            for document in documents
        ]
