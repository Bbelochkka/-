from __future__ import annotations

import time
import uuid

import requests


def unique_suffix() -> str:
    return uuid.uuid4().hex[:8]


def create_course(base_url: str, *, title: str | None = None):
    payload = {
        "title": title or f"Курс по продажам {unique_suffix()}",
        "moduleId": f"SALES-{unique_suffix()[:4].upper()}",
        "description": "Черновик курса для новых сотрудников",
        "createdBy": "teacher-demo",
        "tags": ["sales", "b2b"],
    }
    response = requests.post(f"{base_url}/api/v1/courses", json=payload, timeout=10)
    assert response.status_code == 201, response.text
    return response.json(), payload


def delete_course_if_exists(base_url: str, course_id: str) -> None:
    response = requests.delete(f"{base_url}/api/v1/courses/{course_id}", timeout=10)
    assert response.status_code in (204, 404), response.text


def get_documents(base_url: str):
    response = requests.get(f"{base_url}/api/v1/documents", timeout=10)
    assert response.status_code == 200, response.text
    return response.json()


def create_generation_task(base_url: str, *, title: str | None = None):
    docs = get_documents(base_url)
    assert len(docs) >= 1

    response = requests.post(
        f"{base_url}/api/v1/courses/generate-from-documents",
        json={
            "title": title or f"Сгенерированный курс {unique_suffix()}",
            "documentIds": [docs[0]["id"]],
        },
        timeout=10,
    )
    assert response.status_code == 202, response.text
    return response.json()["taskId"]


def wait_for_task_done(base_url: str, task_id: str):
    for _ in range(15):
        response = requests.get(f"{base_url}/api/v1/tasks/{task_id}", timeout=10)
        assert response.status_code == 200, response.text
        payload = response.json()
        if payload["status"] == "DONE":
            return payload
        if payload["status"] == "FAILED":
            raise AssertionError(payload["error"])
        time.sleep(2)
    raise AssertionError("Worker did not finish task in time")


def test_health(base_url: str):
    response = requests.get(f"{base_url}/health", timeout=10)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "courses-service"


def test_list_seed_documents(base_url: str):
    docs = get_documents(base_url)
    assert len(docs) >= 1
    assert all("id" in item and "title" in item for item in docs)


def test_create_course(base_url: str):
    created_body, payload = create_course(base_url)
    try:
        assert created_body["title"] == payload["title"]
        assert created_body["moduleId"] == payload["moduleId"]
        assert created_body["createdBy"] == payload["createdBy"]
        assert created_body["status"] == "DRAFT"
    finally:
        delete_course_if_exists(base_url, created_body["id"])


def test_list_courses_contains_created_course(base_url: str):
    created_body, payload = create_course(base_url)
    try:
        response = requests.get(f"{base_url}/api/v1/courses", params={"page": 1, "pageSize": 50}, timeout=10)
        assert response.status_code == 200, response.text
        listed_body = response.json()
        assert listed_body["total"] >= 1
        assert any(item["id"] == created_body["id"] for item in listed_body["items"])
        assert any(item["title"] == payload["title"] for item in listed_body["items"])
    finally:
        delete_course_if_exists(base_url, created_body["id"])


def test_update_course(base_url: str):
    created_body, _ = create_course(base_url)
    try:
        updated = requests.put(
            f"{base_url}/api/v1/courses/{created_body['id']}",
            json={"title": "Обновленный курс по продажам", "tags": ["sales", "updated"]},
            timeout=10,
        )
        assert updated.status_code == 200, updated.text
        updated_body = updated.json()
        assert updated_body["title"] == "Обновленный курс по продажам"
        assert updated_body["tags"] == ["sales", "updated"]
    finally:
        delete_course_if_exists(base_url, created_body["id"])


def test_submit_course_changes_status(base_url: str):
    created_body, _ = create_course(base_url)
    try:
        submitted = requests.post(f"{base_url}/api/v1/courses/{created_body['id']}/submit", timeout=10)
        assert submitted.status_code == 200, submitted.text
        assert submitted.json()["status"] == "PENDING_APPROVAL"
    finally:
        delete_course_if_exists(base_url, created_body["id"])


def test_create_generation_task(base_url: str):
    task_id = create_generation_task(base_url)
    response = requests.get(f"{base_url}/api/v1/tasks/{task_id}", timeout=10)
    assert response.status_code == 200, response.text
    task_body = response.json()
    assert task_body["id"] == task_id
    assert task_body["type"] == "GENERATE_COURSE"
    assert task_body["status"] in ["QUEUED", "PROCESSING", "DONE"]


def test_worker_completes_generation_task(base_url: str):
    task_id = create_generation_task(base_url, title=f"Курс для проверки worker {unique_suffix()}")
    done_task = wait_for_task_done(base_url, task_id)
    assert done_task["status"] == "DONE"
    assert "courseId" in done_task["result"]


def test_generated_course_can_be_loaded(base_url: str):
    task_id = create_generation_task(base_url, title=f"Курс для загрузки {unique_suffix()}")
    done_task = wait_for_task_done(base_url, task_id)
    generated_course_id = done_task["result"]["courseId"]

    generated_course = requests.get(f"{base_url}/api/v1/courses/{generated_course_id}", timeout=10)
    assert generated_course.status_code == 200, generated_course.text
    generated_body = generated_course.json()
    assert generated_body["id"] == generated_course_id
    assert generated_body["status"] == "DRAFT"
    assert generated_body["createdBy"] == "worker-service"


def test_delete_course(base_url: str):
    created_body, _ = create_course(base_url)
    deleted = requests.delete(f"{base_url}/api/v1/courses/{created_body['id']}", timeout=10)
    assert deleted.status_code == 204, deleted.text


def test_deleted_course_returns_404(base_url: str):
    created_body, _ = create_course(base_url)
    deleted = requests.delete(f"{base_url}/api/v1/courses/{created_body['id']}", timeout=10)
    assert deleted.status_code == 204, deleted.text

    get_deleted = requests.get(f"{base_url}/api/v1/courses/{created_body['id']}", timeout=10)
    assert get_deleted.status_code == 404, get_deleted.text
    assert get_deleted.json()["code"] == "NOT_FOUND"
