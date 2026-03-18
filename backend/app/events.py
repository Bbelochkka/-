from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol


@dataclass(slots=True)
class DomainEvent:
    name: str
    payload: dict
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class EventListener(Protocol):
    def handle(self, event: DomainEvent) -> None: ...


class EventDispatcher:
    def __init__(self) -> None:
        self._listeners: dict[str, list[EventListener]] = {}

    def subscribe(self, event_name: str, listener: EventListener) -> None:
        self._listeners.setdefault(event_name, []).append(listener)

    def publish(self, event: DomainEvent) -> None:
        for listener in self._listeners.get(event.name, []):
            listener.handle(event)


class AuditLogListener:
    def handle(self, event: DomainEvent) -> None:
        print(f"[AUDIT] {event.name}: {event.payload}")


class MetricsListener:
    def handle(self, event: DomainEvent) -> None:
        print(f"[METRICS] {event.name} at {event.occurred_at.isoformat()}")


class NotificationListener:
    def handle(self, event: DomainEvent) -> None:
        print(f"[NOTIFY] Event '{event.name}' prepared for downstream delivery")



def build_default_dispatcher() -> EventDispatcher:
    dispatcher = EventDispatcher()
    audit = AuditLogListener()
    metrics = MetricsListener()
    notify = NotificationListener()

    for event_name in ("course_created", "course_updated", "course_submitted", "generation_task_created"):
        dispatcher.subscribe(event_name, audit)
        dispatcher.subscribe(event_name, metrics)

    dispatcher.subscribe("course_submitted", notify)
    return dispatcher
