from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .models import Course, CourseStatus, Document, Task, TaskStatus, TaskType


class SqlAlchemyDocumentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_all(self) -> list[Document]:
        return self.db.scalars(select(Document).order_by(Document.created_at.desc())).all()

    def exists_all(self, document_ids: list[str]) -> bool:
        existing = self.db.scalars(select(Document.id).where(Document.id.in_(document_ids))).all()
        return len(existing) == len(document_ids)

    def get_many(self, document_ids: list[str]) -> list[Document]:
        return self.db.scalars(select(Document).where(Document.id.in_(document_ids))).all()


class CachedDocumentRepositoryProxy:
    """Proxy caches document queries during one request/facade lifetime."""

    def __init__(self, target: SqlAlchemyDocumentRepository) -> None:
        self.target = target
        self._all_cache: list[Document] | None = None
        self._many_cache: dict[tuple[str, ...], list[Document]] = {}

    def list_all(self) -> list[Document]:
        if self._all_cache is None:
            self._all_cache = self.target.list_all()
        return self._all_cache

    def exists_all(self, document_ids: list[str]) -> bool:
        return self.target.exists_all(document_ids)

    def get_many(self, document_ids: list[str]) -> list[Document]:
        key = tuple(sorted(document_ids))
        if key not in self._many_cache:
            self._many_cache[key] = self.target.get_many(document_ids)
        return self._many_cache[key]


class SqlAlchemyCourseRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, course: Course) -> Course:
        self.db.add(course)
        self.db.commit()
        self.db.refresh(course)
        return course

    def save(self, course: Course) -> Course:
        self.db.commit()
        self.db.refresh(course)
        return course

    def get_by_id(self, course_id: str) -> Course | None:
        return self.db.get(Course, course_id)

    def delete(self, course: Course) -> None:
        self.db.delete(course)
        self.db.commit()

    def list_paginated(
        self,
        *,
        page: int,
        page_size: int,
        status_filter: CourseStatus | None,
        query: str | None,
    ) -> tuple[list[Course], int]:
        stmt = select(Course)
        count_stmt = select(func.count()).select_from(Course)
        filters = []
        if status_filter:
            filters.append(Course.status == status_filter)
        if query:
            filters.append(or_(Course.title.ilike(f"%{query}%"), Course.description.ilike(f"%{query}%")))
        if filters:
            stmt = stmt.where(*filters)
            count_stmt = count_stmt.where(*filters)
        total = self.db.scalar(count_stmt) or 0
        items = self.db.scalars(
            stmt.order_by(Course.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        ).all()
        return items, total


class LoggingCourseRepositoryDecorator:
    """Decorator adds logging without changing repository contract."""

    def __init__(self, target: SqlAlchemyCourseRepository) -> None:
        self.target = target

    def add(self, course: Course) -> Course:
        print(f"[COURSE-REPO] create course '{course.title}'")
        return self.target.add(course)

    def save(self, course: Course) -> Course:
        print(f"[COURSE-REPO] save course '{course.id}' with status {course.status.value}")
        return self.target.save(course)

    def get_by_id(self, course_id: str) -> Course | None:
        return self.target.get_by_id(course_id)

    def delete(self, course: Course) -> None:
        print(f"[COURSE-REPO] delete course '{course.id}'")
        self.target.delete(course)

    def list_paginated(
        self,
        *,
        page: int,
        page_size: int,
        status_filter: CourseStatus | None,
        query: str | None,
    ) -> tuple[list[Course], int]:
        return self.target.list_paginated(page=page, page_size=page_size, status_filter=status_filter, query=query)


class SqlAlchemyTaskRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, task: Task) -> Task:
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def get_by_id(self, task_id: str) -> Task | None:
        return self.db.get(Task, task_id)


@dataclass(slots=True)
class RepositoryFactory:
    """Factory Method provider for repositories."""

    def create_document_repository(self, db: Session) -> SqlAlchemyDocumentRepository:
        return SqlAlchemyDocumentRepository(db)

    def create_course_repository(self, db: Session) -> SqlAlchemyCourseRepository:
        return SqlAlchemyCourseRepository(db)

    def create_task_repository(self, db: Session) -> SqlAlchemyTaskRepository:
        return SqlAlchemyTaskRepository(db)
