from __future__ import annotations

from abc import ABC, abstractmethod

from .adapters import DocumentFragment


class CourseDescriptionStrategy(ABC):
    @abstractmethod
    def build_description(self, fragments: list[DocumentFragment]) -> str: ...


class SummaryDescriptionStrategy(CourseDescriptionStrategy):
    def build_description(self, fragments: list[DocumentFragment]) -> str:
        topics = "; ".join(fragment.title for fragment in fragments)
        return (
            "Черновик курса сгенерирован на основе документов: "
            f"{topics}. Курс концентрируется на первичном контакте с клиентом, работе в CRM и обработке типовых возражений."
        )


class OutlineDescriptionStrategy(CourseDescriptionStrategy):
    def build_description(self, fragments: list[DocumentFragment]) -> str:
        lines = ["Сгенерированная структура курса:"]
        for index, fragment in enumerate(fragments, start=1):
            preview = fragment.normalized_content[:90]
            lines.append(f"{index}. {fragment.title}: {preview}...")
        return " ".join(lines)


class StrategyResolver:
    def resolve(self, mode: str | None) -> CourseDescriptionStrategy:
        if (mode or "summary").lower() == "outline":
            return OutlineDescriptionStrategy()
        return SummaryDescriptionStrategy()
