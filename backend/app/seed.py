from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Document

SEED_DOCUMENTS = [
    {"title": "Скрипт первичного звонка", "content": "Этапы звонка: приветствие, выявление потребности, презентация продукта, обработка возражений, договоренность о следующем шаге."},
    {"title": "Регламент работы с CRM", "content": "Каждое касание клиента фиксируется в CRM. Обязательные поля: источник лида, статус сделки, дата следующего контакта."},
    {"title": "FAQ по продукту", "content": "Частые вопросы: стоимость, сроки внедрения, варианты тарифа, условия сопровождения и типовые возражения клиентов."},
]


def seed_documents(db: Session) -> None:
    exists = db.scalar(select(Document.id).limit(1))
    if exists:
        return
    for item in SEED_DOCUMENTS:
        db.add(Document(title=item["title"], content=item["content"]))
    db.commit()
