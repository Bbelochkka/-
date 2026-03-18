from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import uuid4

from .events import DomainEvent, EventDispatcher
from .models import Course, CourseStatus, Task, TaskStatus, TaskType
from .state import CourseStateResolver


class Command(ABC):
    @abstractmethod
    def execute(self): ...


class CreateCourseCommand(Command):
    def __init__(self, *, repository, dispatcher: EventDispatcher, payload: dict) -> None:
        self.repository = repository
        self.dispatcher = dispatcher
        self.payload = payload

    def execute(self) -> Course:
        course = Course(
            id=str(uuid4()),
            title=self.payload["title"],
            module_id=self.payload["moduleId"],
            description=self.payload.get("description"),
            created_by=self.payload["createdBy"],
            tags=self.payload.get("tags", []),
            status=CourseStatus.DRAFT,
        )
        created = self.repository.add(course)
        self.dispatcher.publish(DomainEvent(name="course_created", payload={"courseId": created.id}))
        return created


class UpdateCourseCommand(Command):
    def __init__(self, *, repository, dispatcher: EventDispatcher, course: Course, payload: dict) -> None:
        self.repository = repository
        self.dispatcher = dispatcher
        self.course = course
        self.payload = payload

    def execute(self) -> Course:
        if self.payload.get("title") is not None:
            self.course.title = self.payload["title"]
        if self.payload.get("description") is not None:
            self.course.description = self.payload["description"]
        if self.payload.get("tags") is not None:
            self.course.tags = self.payload["tags"]
        if self.payload.get("status") is not None:
            self.course.status = self.payload["status"]
        saved = self.repository.save(self.course)
        self.dispatcher.publish(DomainEvent(name="course_updated", payload={"courseId": saved.id}))
        return saved


class SubmitCourseCommand(Command):
    def __init__(self, *, repository, dispatcher: EventDispatcher, course: Course) -> None:
        self.repository = repository
        self.dispatcher = dispatcher
        self.course = course

    def execute(self) -> Course:
        current_state = CourseStateResolver.resolve(self.course.status)
        updated_course = current_state.submit(self.course)
        saved = self.repository.save(updated_course)
        self.dispatcher.publish(DomainEvent(name="course_submitted", payload={"courseId": saved.id, "status": saved.status.value}))
        return saved


class DeleteCourseCommand(Command):
    def __init__(self, *, repository, course: Course) -> None:
        self.repository = repository
        self.course = course

    def execute(self) -> None:
        self.repository.delete(self.course)


class CreateGenerationTaskCommand(Command):
    def __init__(self, *, repository, dispatcher: EventDispatcher, title: str, document_ids: list[str], generation_mode: str) -> None:
        self.repository = repository
        self.dispatcher = dispatcher
        self.title = title
        self.document_ids = document_ids
        self.generation_mode = generation_mode

    def execute(self) -> Task:
        task = Task(
            id=str(uuid4()),
            type=TaskType.GENERATE_COURSE,
            status=TaskStatus.QUEUED,
            payload={"title": self.title, "documentIds": self.document_ids, "generationMode": self.generation_mode},
            result=None,
            error=None,
        )
        created = self.repository.add(task)
        self.dispatcher.publish(
            DomainEvent(name="generation_task_created", payload={"taskId": created.id, "documents": len(self.document_ids)})
        )
        return created
