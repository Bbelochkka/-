from __future__ import annotations

import time
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from sqlalchemy import func, or_, select, text as sql_text
from sqlalchemy.orm import Session

from .database import Base, SessionLocal, engine, get_db
from .models import Course, CourseStatus, Document, Task, TaskStatus, TaskType
from .schemas import (
    CourseCreateRequest,
    CourseResponse,
    CoursesListResponse,
    CourseUpdateRequest,
    DocumentResponse,
    ErrorResponse,
    GenerateCourseFromDocsRequest,
    GenerateCourseFromDocsResponse,
    HealthResponse,
    TaskResponse,
)
from .seed import seed_documents

app = FastAPI(title="Adaptation System - Courses Service", version="1.0.0")


@app.middleware("http")
async def add_trace_id(request: Request, call_next):
    request.state.trace_id = str(uuid4())
    response = await call_next(request)
    response.headers["X-Trace-Id"] = request.state.trace_id
    return response


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    payload = ErrorResponse(code="VALIDATION_ERROR", message="Validation failed", details=exc.errors(), traceId=request.state.trace_id)
    return JSONResponse(status_code=422, content=payload.model_dump(mode="json"))


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    code = "NOT_FOUND" if exc.status_code == 404 else "HTTP_ERROR"
    payload = ErrorResponse(code=code, message=str(exc.detail), details=[], traceId=request.state.trace_id)
    return JSONResponse(status_code=exc.status_code, content=payload.model_dump(mode="json"))


@app.on_event("startup")
def on_startup() -> None:
    last_error = None
    for _ in range(20):
        try:
            with engine.connect() as conn:
                conn.execute(sql_text("SELECT 1"))
            Base.metadata.create_all(bind=engine)
            with SessionLocal() as db:
                seed_documents(db)
            return
        except Exception as exc:
            last_error = exc
            time.sleep(2)
    raise RuntimeError(f"Database is not available: {last_error}")


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="courses-service", time=datetime.now(timezone.utc))


@app.get("/api/v1/documents", response_model=list[DocumentResponse])
def list_documents(db: Session = Depends(get_db)) -> list[DocumentResponse]:
    items = db.scalars(select(Document).order_by(Document.created_at.desc())).all()
    return [DocumentResponse(id=x.id, title=x.title, createdAt=x.created_at) for x in items]


@app.post("/api/v1/courses", response_model=CourseResponse, status_code=status.HTTP_201_CREATED)
def create_course(req: CourseCreateRequest, db: Session = Depends(get_db)) -> CourseResponse:
    course = Course(title=req.title, module_id=req.moduleId, description=req.description, created_by=req.createdBy, tags=req.tags, status=CourseStatus.DRAFT)
    db.add(course)
    db.commit()
    db.refresh(course)
    return to_course_response(course)


@app.get("/api/v1/courses", response_model=CoursesListResponse)
def list_courses(page: int = Query(1, ge=1), pageSize: int = Query(10, ge=1, le=100), status_filter: CourseStatus | None = Query(None, alias="status"), q: str | None = Query(None, min_length=2), db: Session = Depends(get_db)) -> CoursesListResponse:
    stmt = select(Course)
    count_stmt = select(func.count()).select_from(Course)
    filters = []
    if status_filter:
        filters.append(Course.status == status_filter)
    if q:
        filters.append(or_(Course.title.ilike(f"%{q}%"), Course.description.ilike(f"%{q}%")))
    if filters:
        stmt = stmt.where(*filters)
        count_stmt = count_stmt.where(*filters)
    total = db.scalar(count_stmt) or 0
    items = db.scalars(stmt.order_by(Course.created_at.desc()).offset((page - 1) * pageSize).limit(pageSize)).all()
    return CoursesListResponse(items=[to_course_response(item) for item in items], page=page, pageSize=pageSize, total=total)


@app.get("/api/v1/courses/{course_id}", response_model=CourseResponse)
def get_course(course_id: str, db: Session = Depends(get_db)) -> CourseResponse:
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return to_course_response(course)


@app.put("/api/v1/courses/{course_id}", response_model=CourseResponse)
def update_course(course_id: str, req: CourseUpdateRequest, db: Session = Depends(get_db)) -> CourseResponse:
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    if req.title is not None:
        course.title = req.title
    if req.description is not None:
        course.description = req.description
    if req.tags is not None:
        course.tags = req.tags
    if req.status is not None:
        course.status = req.status
    db.commit()
    db.refresh(course)
    return to_course_response(course)


@app.post("/api/v1/courses/{course_id}/submit", response_model=CourseResponse)
def submit_course(course_id: str, db: Session = Depends(get_db)) -> CourseResponse:
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    course.status = CourseStatus.PENDING_APPROVAL
    db.commit()
    db.refresh(course)
    return to_course_response(course)


@app.delete("/api/v1/courses/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_course(course_id: str, db: Session = Depends(get_db)) -> Response:
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    db.delete(course)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/api/v1/courses/generate-from-documents", response_model=GenerateCourseFromDocsResponse, status_code=status.HTTP_202_ACCEPTED)
def generate_from_documents(req: GenerateCourseFromDocsRequest, db: Session = Depends(get_db)) -> GenerateCourseFromDocsResponse:
    doc_ids = [str(x) for x in req.documentIds]
    existing = db.scalars(select(Document.id).where(Document.id.in_(doc_ids))).all()
    if len(existing) != len(doc_ids):
        raise HTTPException(status_code=404, detail="One or more documents not found")
    task = Task(type=TaskType.GENERATE_COURSE, status=TaskStatus.QUEUED, payload={"title": req.title, "documentIds": doc_ids}, result=None, error=None)
    db.add(task)
    db.commit()
    db.refresh(task)
    return GenerateCourseFromDocsResponse(taskId=task.id)


@app.get("/api/v1/tasks/{task_id}", response_model=TaskResponse)
def get_task(task_id: str, db: Session = Depends(get_db)) -> TaskResponse:
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskResponse(id=task.id, type=task.type, status=task.status, payload=task.payload, result=task.result, error=task.error, createdAt=task.created_at, updatedAt=task.updated_at)


def to_course_response(course: Course) -> CourseResponse:
    return CourseResponse(id=course.id, title=course.title, moduleId=course.module_id, description=course.description, createdBy=course.created_by, tags=course.tags or [], status=course.status, createdAt=course.created_at, updatedAt=course.updated_at)
