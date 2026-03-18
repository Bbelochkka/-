from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .adapters import DocumentContentAdapter
from .builders import GeneratedCourseBuilder
from .models import Course, Document, Task, TaskStatus, TaskType
from .strategies import StrategyResolver


class BaseTaskProcessor(ABC):
    """Template Method: describes common processing algorithm for any task."""

    def __init__(self) -> None:
        self.adapter = DocumentContentAdapter()
        self.strategy_resolver = StrategyResolver()

    def process(self, db: Session, task: Task) -> Course:
        self.mark_processing(db, task)
        payload = self.read_payload(task)
        documents = self.load_documents(db, payload)
        course = self.build_course(payload, documents)
        self.persist_course(db, course)
        self.mark_done(task, course)
        return course

    def mark_processing(self, db: Session, task: Task) -> None:
        task.status = TaskStatus.PROCESSING
        task.updated_at = datetime.now(timezone.utc)
        db.flush()

    def read_payload(self, task: Task) -> dict:
        return task.payload

    def load_documents(self, db: Session, payload: dict) -> list[Document]:
        doc_ids = payload["documentIds"]
        documents = db.scalars(select(Document).where(Document.id.in_(doc_ids))).all()
        if not documents:
            raise ValueError("No documents found for generation")
        return documents

    @abstractmethod
    def supports(self, task_type: TaskType) -> bool: ...

    @abstractmethod
    def build_course(self, payload: dict, documents: list[Document]) -> Course: ...

    def persist_course(self, db: Session, course: Course) -> None:
        db.add(course)
        db.flush()

    def mark_done(self, task: Task, course: Course) -> None:
        task.status = TaskStatus.DONE
        task.result = {"courseId": course.id}
        task.error = None
        task.updated_at = datetime.now(timezone.utc)

    def mark_failed(self, task: Task, exc: Exception) -> None:
        task.status = TaskStatus.FAILED
        task.error = str(exc)
        task.updated_at = datetime.now(timezone.utc)


class GenerateCourseTaskProcessor(BaseTaskProcessor):
    def supports(self, task_type: TaskType) -> bool:
        return task_type == TaskType.GENERATE_COURSE

    def build_course(self, payload: dict, documents: list[Document]) -> Course:
        fragments = self.adapter.adapt(documents)
        strategy = self.strategy_resolver.resolve(payload.get("generationMode"))
        description = strategy.build_description(fragments)
        tags = ["generated", "sales", payload.get("generationMode", "summary").lower()]
        return (
            GeneratedCourseBuilder()
            .with_title(payload["title"])
            .with_description(description)
            .with_tags(tags)
            .build()
        )


class TaskProcessorFactory:
    """Factory Method: selects processor for a concrete task type."""

    def create(self, task: Task) -> BaseTaskProcessor:
        candidates: list[BaseTaskProcessor] = [GenerateCourseTaskProcessor()]
        for candidate in candidates:
            if candidate.supports(task.type):
                return candidate
        raise ValueError(f"No processor for task type {task.type.value}")
