from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from .models import CourseStatus, TaskStatus, TaskType


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: list[Any] = Field(default_factory=list)
    traceId: str


class CourseCreateRequest(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    moduleId: str = Field(min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=4000)
    createdBy: str = Field(min_length=2, max_length=100)
    tags: list[str] = Field(default_factory=list)


class CourseUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    tags: list[str] | None = None
    status: CourseStatus | None = None


class CourseResponse(BaseModel):
    id: str
    title: str
    moduleId: str
    description: str | None
    createdBy: str
    tags: list[str]
    status: CourseStatus
    createdAt: datetime
    updatedAt: datetime


class CoursesListResponse(BaseModel):
    items: list[CourseResponse]
    page: int
    pageSize: int
    total: int


class DocumentResponse(BaseModel):
    id: str
    title: str
    createdAt: datetime


class GenerateCourseFromDocsRequest(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    documentIds: list[UUID] = Field(min_length=1)


class GenerateCourseFromDocsResponse(BaseModel):
    taskId: str


class TaskResponse(BaseModel):
    id: str
    type: TaskType
    status: TaskStatus
    payload: dict[str, Any]
    result: dict[str, Any] | None
    error: str | None
    createdAt: datetime
    updatedAt: datetime


class HealthResponse(BaseModel):
    status: str
    service: str
    time: datetime
