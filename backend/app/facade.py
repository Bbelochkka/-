from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from .commands import (
    CreateCourseCommand,
    CreateGenerationTaskCommand,
    DeleteCourseCommand,
    SubmitCourseCommand,
    UpdateCourseCommand,
)
from .config import AppConfig
from .events import build_default_dispatcher
from .models import CourseStatus, Task
from .repositories import (
    CachedDocumentRepositoryProxy,
    LoggingCourseRepositoryDecorator,
    RepositoryFactory,
)


@dataclass
class CourseFacade:
    db: Session

    def __post_init__(self) -> None:
        self.config = AppConfig.get_instance()
        self.dispatcher = build_default_dispatcher()
        self.factory = RepositoryFactory()
        self.document_repository = CachedDocumentRepositoryProxy(self.factory.create_document_repository(self.db))
        self.course_repository = LoggingCourseRepositoryDecorator(self.factory.create_course_repository(self.db))
        self.task_repository = self.factory.create_task_repository(self.db)

    def list_documents(self):
        return self.document_repository.list_all()

    def create_course(self, payload: dict):
        return CreateCourseCommand(repository=self.course_repository, dispatcher=self.dispatcher, payload=payload).execute()

    def list_courses(self, *, page: int, page_size: int, status_filter: CourseStatus | None, query: str | None):
        return self.course_repository.list_paginated(page=page, page_size=page_size, status_filter=status_filter, query=query)

    def get_course(self, course_id: str):
        return self.course_repository.get_by_id(course_id)

    def update_course(self, course, payload: dict):
        return UpdateCourseCommand(repository=self.course_repository, dispatcher=self.dispatcher, course=course, payload=payload).execute()

    def submit_course(self, course):
        return SubmitCourseCommand(repository=self.course_repository, dispatcher=self.dispatcher, course=course).execute()

    def delete_course(self, course) -> None:
        DeleteCourseCommand(repository=self.course_repository, course=course).execute()

    def create_generation_task(self, *, title: str, document_ids: list[str], generation_mode: str | None = None) -> Task:
        mode = generation_mode or self.config.default_generation_mode
        return CreateGenerationTaskCommand(
            repository=self.task_repository,
            dispatcher=self.dispatcher,
            title=title,
            document_ids=document_ids,
            generation_mode=mode,
        ).execute()

    def get_task(self, task_id: str):
        return self.task_repository.get_by_id(task_id)

    def validate_documents_exist(self, document_ids: list[str]) -> bool:
        return self.document_repository.exists_all(document_ids)
