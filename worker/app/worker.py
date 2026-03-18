from __future__ import annotations

import os
import time

from sqlalchemy import select

from .database import session_scope
from .models import Task, TaskStatus
from .processors import TaskProcessorFactory

POLL_INTERVAL_SECONDS = float(os.getenv("POLL_INTERVAL_SECONDS", "3"))


def process_once() -> bool:
    with session_scope() as db:
        task = db.scalars(
            select(Task).where(Task.status == TaskStatus.QUEUED).order_by(Task.created_at.asc()).limit(1)
        ).first()
        if not task:
            return False

        processor = TaskProcessorFactory().create(task)
        try:
            processor.process(db, task)
        except Exception as exc:
            processor.mark_failed(task, exc)
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
