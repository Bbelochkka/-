from __future__ import annotations

import uuid
from datetime import datetime, timezone

from .models import Course, CourseStatus


class GeneratedCourseBuilder:
    """Builder assembles a generated course step by step."""

    def __init__(self) -> None:
        self._data: dict = {
            "id": str(uuid.uuid4()),
            "module_id": "AUTO-GEN",
            "created_by": "worker-service",
            "tags": ["generated", "sales", "adaptation"],
            "status": CourseStatus.DRAFT,
        }

    def with_title(self, title: str) -> "GeneratedCourseBuilder":
        self._data["title"] = title
        return self

    def with_description(self, description: str) -> "GeneratedCourseBuilder":
        self._data["description"] = description
        return self

    def with_tags(self, tags: list[str]) -> "GeneratedCourseBuilder":
        self._data["tags"] = tags
        return self

    def build(self) -> Course:
        now = datetime.now(timezone.utc)
        return Course(
            id=self._data["id"],
            title=self._data["title"],
            module_id=self._data["module_id"],
            description=self._data["description"],
            created_by=self._data["created_by"],
            tags=self._data["tags"],
            status=self._data["status"],
            created_at=now,
            updated_at=now,
        )
