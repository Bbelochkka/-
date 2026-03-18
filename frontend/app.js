const documentsList = document.getElementById('documentsList');
const coursesList = document.getElementById('coursesList');
const generateBtn = document.getElementById('generateBtn');
const refreshAllBtn = document.getElementById('refreshAllBtn');
const reloadCoursesBtn = document.getElementById('reloadCoursesBtn');
const taskResult = document.getElementById('taskResult');
const courseTitleInput = document.getElementById('courseTitleInput');

async function api(path, init) {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(error || response.statusText);
  }

  if (response.status === 204) return null;
  return response.json();
}

async function loadDocuments() {
  const docs = await api('/api/v1/documents');
  documentsList.innerHTML = '';

  docs.forEach((doc) => {
    const label = document.createElement('label');
    label.className = 'doc-item';
    label.innerHTML = `
      <div><strong>${doc.title}</strong></div>
      <div class="hint">ID: ${doc.id}</div>
      <div class="hint">Добавлен: ${new Date(doc.createdAt).toLocaleString('ru-RU')}</div>
      <div style="margin-top:10px;"><input type="checkbox" value="${doc.id}" checked /> Использовать в генерации</div>
    `;
    documentsList.appendChild(label);
  });
}

function getSubmitButtonState(course) {
  switch (course.status) {
    case 'DRAFT':
      return { text: 'Отправить на согласование', disabled: false, extraClass: '' };
    case 'PENDING_APPROVAL':
      return { text: 'Уже отправлено на согласование', disabled: true, extraClass: 'is-disabled-state' };
    case 'APPROVED':
      return { text: 'Курс уже согласован', disabled: true, extraClass: 'is-success-state' };
    case 'ARCHIVED':
      return { text: 'Архивный курс', disabled: true, extraClass: 'is-disabled-state' };
    default:
      return { text: 'Отправить на согласование', disabled: true, extraClass: 'is-disabled-state' };
  }
}

function courseTemplate(course) {
  const submitState = getSubmitButtonState(course);
  const wrapper = document.createElement('article');
  wrapper.className = 'course-item';
  wrapper.innerHTML = `
    <div class="row-between">
      <strong>${course.title}</strong>
      <span class="badge">${course.status}</span>
    </div>
    <div class="hint">ID: ${course.id}</div>
    <div class="hint">Модуль: ${course.moduleId}</div>
    <p>${course.description ?? 'Без описания'}</p>
    <div class="actions">
      <button data-action="submit" class="${submitState.extraClass}" ${submitState.disabled ? 'disabled' : ''}>${submitState.text}</button>
      <button data-action="delete">Удалить</button>
    </div>
  `;

  const submitBtn = wrapper.querySelector('[data-action="submit"]');
  const deleteBtn = wrapper.querySelector('[data-action="delete"]');

  submitBtn.addEventListener('click', async () => {
    if (submitBtn.disabled) return;

    submitBtn.disabled = true;
    submitBtn.textContent = 'Отправляем...';

    try {
      await api(`/api/v1/courses/${course.id}/submit`, { method: 'POST' });
      taskResult.textContent = `Курс «${course.title}» отправлен на согласование.`;
      await loadCourses();
    } catch (error) {
      submitBtn.disabled = false;
      submitBtn.textContent = 'Отправить на согласование';
      taskResult.textContent = `Ошибка при отправке на согласование: ${error.message}`;
    }
  });

  deleteBtn.addEventListener('click', async () => {
    await api(`/api/v1/courses/${course.id}`, { method: 'DELETE' });
    taskResult.textContent = `Курс «${course.title}» удалён.`;
    await loadCourses();
  });

  return wrapper;
}

async function loadCourses() {
  const data = await api('/api/v1/courses?page=1&pageSize=20');
  coursesList.innerHTML = '';

  if (!data.items.length) {
    coursesList.innerHTML = '<div class="hint">Курсы пока отсутствуют.</div>';
    return;
  }

  data.items.forEach((course) => coursesList.appendChild(courseTemplate(course)));
}

async function pollTask(taskId) {
  const start = Date.now();

  while (Date.now() - start < 30000) {
    const task = await api(`/api/v1/tasks/${taskId}`);
    if (task.status === 'DONE') return task;
    if (task.status === 'FAILED') throw new Error(task.error || 'Task failed');
    await new Promise((resolve) => setTimeout(resolve, 2000));
  }

  throw new Error('Worker did not complete task in time');
}

async function generateCourse() {
  const checked = Array.from(documentsList.querySelectorAll('input[type="checkbox"]:checked')).map((el) => el.value);

  if (!checked.length) {
    taskResult.textContent = 'Выбери хотя бы один документ.';
    return;
  }

  generateBtn.disabled = true;
  taskResult.textContent = 'Создание задачи на генерацию...';

  try {
    const task = await api('/api/v1/courses/generate-from-documents', {
      method: 'POST',
      body: JSON.stringify({ title: courseTitleInput.value, documentIds: checked }),
    });
    taskResult.textContent = `Задача ${task.taskId} создана. Ожидаем worker...`;
    const doneTask = await pollTask(task.taskId);
    taskResult.textContent = `Готово. Worker создал курс ${doneTask.result.courseId}.`;
    await loadCourses();
  } catch (error) {
    taskResult.textContent = `Ошибка: ${error.message}`;
  } finally {
    generateBtn.disabled = false;
  }
}

async function refreshAll() {
  await loadDocuments();
  await loadCourses();
}

generateBtn.addEventListener('click', generateCourse);
refreshAllBtn.addEventListener('click', refreshAll);
reloadCoursesBtn.addEventListener('click', loadCourses);

refreshAll();