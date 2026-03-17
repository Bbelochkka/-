from __future__ import annotations

import os
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from .database import session_scope
from .models import Course, CourseStatus, Document, Task, TaskStatus, TaskType

POLL_INTERVAL_SECONDS = float(os.getenv("POLL_INTERVAL_SECONDS", "3"))


def generate_course_description(documents: list[Document]) -> str:
    topics = "; ".join(doc.title for doc in documents)
    return (
        "Черновик курса сгенерирован фоновым обработчиком на основе документов: "
        f"{topics}. Внутри курса менеджер изучает процесс первичного контакта, правила работы в CRM и ответы на частые вопросы клиентов."
    )


def process_once() -> bool:
    with session_scope() as db:
        task = db.scalars(
            select(Task).where(Task.status == TaskStatus.QUEUED, Task.type == TaskType.GENERATE_COURSE).order_by(Task.created_at.asc()).limit(1)
        ).first()
        if not task:
            return False
        task.status = TaskStatus.PROCESSING
        task.updated_at = datetime.now(timezone.utc)
        db.flush()
        try:
            doc_ids = task.payload["documentIds"]
            title = task.payload["title"]
            documents = db.scalars(select(Document).where(Document.id.in_(doc_ids))).all()
            if not documents:
                raise ValueError("No documents found for generation")
            now = datetime.now(timezone.utc)
            course = Course(
                id=str(uuid.uuid4()),
                title=title,
                module_id="AUTO-GEN",
                description=generate_course_description(documents),
                created_by="worker-service",
                tags=["generated", "sales", "adaptation"],
                status=CourseStatus.DRAFT,
                created_at=now,
                updated_at=now,
            )
            db.add(course)
            db.flush()
            task.status = TaskStatus.DONE
            task.result = {"courseId": course.id}
            task.updated_at = datetime.now(timezone.utc)
        except Exception as exc:
            task.status = TaskStatus.FAILED
            task.error = str(exc)
            task.updated_at = datetime.now(timezone.utc)
        return True


def main() -> None:
    print("Worker started")
    while True:
        try:
            processed = process_once()
            if not processed:
                time.sleep(POLL_INTERVAL_SECONDS)
        except Exception as exc:
            print(f"Worker retry after error: {exc}")
            time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
