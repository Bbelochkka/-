# Лабораторная работа №3

## Тема
Использование принципов проектирования на уровне методов и классов

## Цель работы
Получить опыт проектирования и реализации модулей с использованием принципов KISS, YAGNI, DRY, SOLID и др.

## Выбранный вариант использования
**«Генерация курса на основе загруженных документов и отправка на утверждение руководителю»**.

Сценарий:
1) Руководитель/методист отдела продаж загружает документы (регламенты, скрипты, FAQ).  
2) В веб-интерфейсе запускает генерацию **курса** по выбранным документам.  
3) Система ставит задачу в очередь, фоновый обработчик генерирует структуру курса/уроки через LLM и сохраняет результат.  
4) Руководитель получает уведомление и утверждает/отклоняет курс.

---

## Диаграмма контейнеров
Диаграмма контейнеров **взята из ЛР2.** 
<img width="1920" height="1080" alt="di2" src="https://github.com/user-attachments/assets/784f80f0-b2ed-4464-b077-a08fc7181bc1" />

---

## Диаграмма компонентов
Диаграмма компонентов контейнера «Backend API-приложение» **взята из ЛР2.**  
В дальнейшем в коде демонстрируются принципы проектирования на примере логики, соответствующей компонентам:
- **documents (Компонент управления документами)** — доступ к документам (метаданные + текст),
- **courses (Компонент управления курсами)** — создание/хранение курсов и уроков,
- **tasksOrchestrator (Компонент оркестрации задач)** — постановка фоновых задач,
- **integrations / worker (Компонент интеграционного API)** — интеграция с LLM и выполнение фоновой генерации,
- **auth (Компонент аутентификации и авторизации)** — контроль доступа (роль руководителя).

<img width="1911" height="657" alt="di3" src="https://github.com/user-attachments/assets/32e995ee-1d04-49bf-a172-a8ee72c36d73" />

---

## Диаграмма последовательностей
Диаграмма показывает взаимодействие **C4-компонентов** при генерации курса по документам.
Схема упрощена: оставлены только ключевые компоненты и точки интеграции, без детализации внутреннего хранения файлов и множества таблиц.

<img width="1948" height="902" alt="diSEQ" src="https://github.com/user-attachments/assets/326784e4-6dd0-41c4-8cf8-e7675ae46bf2" />

**Пояснение к диаграмме:**
- **SPA (Web)**: только UI — ввод названия и выбор документов, показ `taskId` и статуса.
- **auth**: RBAC-проверка (в этом сценарии генерацию и утверждение может запускать только руководитель).
- **courses**: API-компонент «точка входа» для команды генерации и место сохранения результата (курс + уроки).
- **tasksOrchestrator**: отвечает за постановку задачи (запись `Task` в БД + отправка `taskId` в очередь).
- **worker**: выполняет долгую работу вне HTTP (получение текста документов, вызов LLM, сохранение результата).
- **documents**: скрывает детали хранения; worker получает уже «готовый текст».
- **Task Queue**: обеспечивает асинхронность, чтобы UI не «висел» на генерации.
- **notificationSystem**: сообщает руководителю, что черновик готов и можно переходить к утверждению.
- **DB** показана одной сущностью для читаемости (по факту сохраняются курс и уроки, а также статус задачи).

---

## Модель БД
Ниже приведена  модель хранения, сфокусированная на сценарии «генерация курса → утверждение».
<img width="867" height="744" alt="diBD" src="https://github.com/user-attachments/assets/020f14cc-5345-4cce-8ac5-b2f550a373c1" />


**Пояснение к модели:**
- **User / Role**: пользователи и роли для контроля доступа (руководитель запускает генерацию и утверждает).
- **Document**: загруженные материалы. `fileKey` — ссылка на файл, `checksum` — быстрый признак изменения (можно использовать для повторной генерации).
- **Course**: генерируемый курс и его статус жизненного цикла (`Draft → PendingApproval → Approved/Rejected`).
- **Lesson**: уроки курса. Вынесены отдельно, чтобы хранить структуру и порядок.
- **Task**: учёт фоновой генерации. `payload` хранит вход (docIds, title), `result` — ссылку на созданный курс.
- **ApprovalRequest**: отдельная сущность для процесса утверждения и комментария руководителя.

---

## Применение основных принципов разработки

Ниже приведены фрагменты **клиентского** и **серверного** кода, реализующие описанный вариант использования, и пояснения, какие принципы учтены.

### 1) Клиентский код (SPA)

#### 1.1 DRY + KISS: единый API-клиент и простая форма

```ts
// api/client.ts
export type ApiError = { status: number; message: string };

export async function apiFetch<T>(
  input: string,
  init?: RequestInit
): Promise<T> {
  const res = await fetch(input, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw { status: res.status, message: text || res.statusText } as ApiError;
  }

  return (await res.json()) as T;
}
```

```tsx
// features/courses/GenerateCourseButton.tsx
import React, { useState } from "react";
import { apiFetch } from "../../api/client";

type GenerateReq = {
  title: string;
  documentIds: string[];
};

type GenerateResp = {
  taskId: string;
};

export function GenerateCourseButton(props: { documentIds: string[] }) {
  const [title, setTitle] = useState("Курс по материалам отдела продаж");
  const [loading, setLoading] = useState(false);
  const [taskId, setTaskId] = useState<string | null>(null);

  async function onGenerate() {
    setLoading(true);
    try {
      const body: GenerateReq = { title, documentIds: props.documentIds };
      const resp = await apiFetch<GenerateResp>("/api/courses/generate-from-documents", {
        method: "POST",
        body: JSON.stringify(body),
      });
      setTaskId(resp.taskId);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <input value={title} onChange={(e) => setTitle(e.target.value)} />
      <button disabled={loading || props.documentIds.length === 0} onClick={onGenerate}>
        {loading ? "Генерация..." : "Сгенерировать курс"}
      </button>
      {taskId && <p>Задача поставлена в очередь: {taskId}</p>}
    </div>
  );
}
```

**Как учтены принципы:**
- **DRY:** единая `apiFetch` убирает дублирование заголовков и обработки ошибок.
- **KISS:** минимум UI‑логики — только нужные поля и кнопка.
- **YAGNI:** нет «универсального конструктора форм» и сложного state‑management — это можно добавить позже при реальной необходимости.

---

### 2) Серверный код (Backend API) и worker

Используется структура: **тонкие контроллеры → сервисы/фасады → репозитории**, а интеграции и очередь задаются через интерфейсы (DIP).

#### 2.1 DTO + валидация (KISS, DRY)

```py
# app/contracts/courses.py
from pydantic import BaseModel, Field, UUID4, conlist

class GenerateCourseFromDocsRequest(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    document_ids: conlist(UUID4, min_length=1)

class GenerateCourseFromDocsResponse(BaseModel):
    task_id: UUID4
```

#### 2.2 Контроллер (SRP, KISS)

```py
# app/api/routes/courses.py
from fastapi import APIRouter, Depends
from app.contracts.courses import (
    GenerateCourseFromDocsRequest,
    GenerateCourseFromDocsResponse,
)
from app.security.auth import require_role
from app.services.course_generation import CourseGenerationFacade

router = APIRouter(prefix="/courses", tags=["courses"])

@router.post("/generate-from-documents", response_model=GenerateCourseFromDocsResponse, status_code=202)
def generate_from_documents(
    req: GenerateCourseFromDocsRequest,
    _user = Depends(require_role("HeadOfSales")),
    facade: CourseGenerationFacade = Depends(),
) -> GenerateCourseFromDocsResponse:
    task_id = facade.request_generation(title=req.title, document_ids=req.document_ids)
    return GenerateCourseFromDocsResponse(task_id=task_id)
```

- **SRP:** контроллер не делает генерацию — только принимает запрос и делегирует.
- **KISS:** минимум ветвлений и логики.

#### 2.3 Фасад/сервис (SOLID: DIP, OCP, ISP)

```py
# app/services/course_generation.py
from dataclasses import dataclass
from typing import Protocol, Iterable
from uuid import UUID

class TaskQueue(Protocol):
    def enqueue(self, task_id: UUID) -> None: ...

class TaskRepository(Protocol):
    def create_generate_course_task(self, title: str, document_ids: list[UUID]) -> UUID: ...

class DocumentRepository(Protocol):
    def ensure_accessible(self, document_ids: Iterable[UUID]) -> None: ...

@dataclass
class CourseGenerationFacade:
    docs: DocumentRepository
    tasks: TaskRepository
    queue: TaskQueue

    def request_generation(self, title: str, document_ids: list[UUID]) -> UUID:
        self.docs.ensure_accessible(document_ids)
        task_id = self.tasks.create_generate_course_task(title=title, document_ids=document_ids)
        self.queue.enqueue(task_id)
        return task_id
```

- **DIP:** зависимости — интерфейсы, а конкретика подключается в DI.
- **ISP:** маленькие интерфейсы вместо «огромного репозитория на всё».
- **OCP:** можно заменить очередь/БД/хранилище, не меняя фасад.

#### 2.4 Репозиторий задач (DRY, SRP)

```py
# app/infra/repositories/tasks_pg.py
from uuid import UUID, uuid4
import json

class PgTaskRepository:
    def __init__(self, conn):
        self._conn = conn

    def create_generate_course_task(self, title: str, document_ids: list[UUID]) -> UUID:
        task_id = uuid4()
        payload = {"title": title, "documentIds": [str(x) for x in document_ids]}
        self._conn.execute(
            "INSERT INTO tasks(id, type, status, payload) VALUES (%s, %s, %s, %s)",
            (str(task_id), "GenerateCourse", "Queued", json.dumps(payload)),
        )
        return task_id
```

- **SRP:** отвечает только за работу с таблицей `tasks`.
- **DRY:** единый формат `payload` для всех задач данного типа.

#### 2.5 Worker: обработка задачи и интеграция с LLM (SoC, SRP, DIP)

```py
# worker/app/llm_client.py
from typing import Protocol

class LLMClient(Protocol):
    def generate_course(self, documents_text: str) -> dict: ...

class YandexGptClient:
    def __init__(self, http):
        self._http = http

    def generate_course(self, documents_text: str) -> dict:
        resp = self._http.post("/generate", json={"prompt": documents_text})
        resp.raise_for_status()
        return resp.json()
```

```py
# worker/app/handler.py
from dataclasses import dataclass
from uuid import UUID

@dataclass
class GenerateCourseHandler:
    llm: "LLMClient"
    task_repo: "TaskRepository"
    storage: "DocumentStorage"
    course_repo: "CourseRepository"
    notifier: "Notifier"

    def handle(self, task_id: UUID) -> None:
        task = self.task_repo.get(task_id)

        docs_text = self.storage.load_as_text(task.payload["documentIds"])
        draft = self.llm.generate_course(docs_text)

        course_id = self.course_repo.save_generated_course(
            title=task.payload["title"],
            draft=draft,
            generated_by_task_id=task_id,
        )

        self.task_repo.mark_done(task_id, result={"courseId": str(course_id)})
        self.notifier.notify_head("Черновик курса готов", {"courseId": str(course_id)})
```

**Как учтены принципы:**
- **SoC / SRP:** интеграция с LLM изолирована в `LLMClient`, сохранение — в `course_repo`, уведомления — в `notifier`.
- **DIP:** handler зависит от интерфейсов, удобно тестировать подменами.
- **YAGNI:** нет ретраев/сложных оркестраций/саг — для MVP достаточно очереди и одной задачи.

---

### SOLID — краткая проверка по буквам

- **S:** контроллер / фасад / репозитории / handler разделены по ответственности.  
- **O:** новые реализации очереди/LLM/репозитория подключаются без изменения бизнес-логики.  
- **L:** любая реализация `LLMClient` может подменять `YandexGptClient`, если соблюдает контракт.  
- **I:** интерфейсы узкие и понятные.  
- **D:** зависимости направлены «к абстракциям», а не к конкретным классам.

---

## Дополнительные принципы разработки

### BDUF — Big Design Up Front
**Отказ (частичный).** Полное проектирование всей системы заранее невыгодно из‑за неопределённости (качество генерации LLM, формат материалов, процесс утверждения).  
**Но** базовое проектирование выполнено: границы компонентов (C4), основные сущности хранения и поток генерации — этого достаточно, чтобы не накапливать хаос.

### SoC — Separation of Concerns
**Применяется.** UI отделён от API, синхронный API — от асинхронной генерации (worker), а доступ к данным и интеграции — от бизнес‑логики.

### MVP — Minimum Viable Product
**Применяется.** Минимально жизнеспособная версия для сценария:
- загрузка документов,
- запуск генерации курса,
- сохранение уроков,
- уведомление и утверждение.

### PoC — Proof of Concept
**Применяется на раннем этапе.** Для LLM целесообразно сначала проверить на реальных документах:
- достаточность качества структуры/уроков,
- скорость/стоимость,
- ограничения и формат промптов.  
После PoC — стабилизация (логирование, ограничения, мониторинг, ретраи).


