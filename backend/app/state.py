from __future__ import annotations

from abc import ABC

from .models import Course, CourseStatus


class CourseWorkflowState(ABC):
    status: CourseStatus

    def submit(self, course: Course) -> Course:
        raise ValueError(f"Transition from {self.status.value} by submit() is not allowed")


class DraftState(CourseWorkflowState):
    status = CourseStatus.DRAFT

    def submit(self, course: Course) -> Course:
        course.status = CourseStatus.PENDING_APPROVAL
        return course


class PendingApprovalState(CourseWorkflowState):
    status = CourseStatus.PENDING_APPROVAL


class ApprovedState(CourseWorkflowState):
    status = CourseStatus.APPROVED


class ArchivedState(CourseWorkflowState):
    status = CourseStatus.ARCHIVED


_STATE_MAP: dict[CourseStatus, CourseWorkflowState] = {
    CourseStatus.DRAFT: DraftState(),
    CourseStatus.PENDING_APPROVAL: PendingApprovalState(),
    CourseStatus.APPROVED: ApprovedState(),
    CourseStatus.ARCHIVED: ArchivedState(),
}


class CourseStateResolver:
    @staticmethod
    def resolve(status: CourseStatus) -> CourseWorkflowState:
        return _STATE_MAP[status]
