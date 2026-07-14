# Учёт замечаний

Веб-приложение для ведения карточек замечаний к объектам и распределения задач по отделам (для ГИП).

## Архитектура (v2)

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────────────────┐
│   Nginx     │────▶│   Frontend   │     │  React SPA (статика)        │
│  :80        │     │  (Vite build)│     └─────────────────────────────┘
└──────┬──────┘     └──────────────┘
       │ /api/*
       ▼
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│  Gunicorn   │────▶│  PostgreSQL  │     │    Redis     │
│  4 workers  │     │  (основная БД)│     │  (кэш, jobs) │
│  FastAPI    │     └──────────────┘     └──────────────┘
└─────────────┘
```

**Рассчитано на ~500 одновременных пользователей:**
- PostgreSQL вместо SQLite (параллельные записи, connection pool)
- Redis-кэш для статистики, справочников и метаданных
- Пагинация списка замечаний (50 на страницу)
- Фоновый импорт Excel (не блокирует API)
- 4+ Gunicorn workers за Nginx
- Индексы на ключевых полях БД

## Быстрый запуск (разработка, Windows)

1. Установите [Python 3.12+](https://www.python.org/downloads/) и [Node.js](https://nodejs.org/)
2. Дважды кликните **`start.bat`**
3. Откройте: **http://127.0.0.1:5173**

Для разработки используется SQLite (файл `backend/zamechaniya.db`). Redis опционален — без него кэш отключается.

## Production (Docker)

```bash
# Скопируйте и настройте переменные
cp backend/.env.example .env

# Запуск
docker compose up -d --build

# Приложение: http://localhost
```

Переменные в `.env`:
- `JWT_SECRET` — обязательно смените
- `POSTGRES_PASSWORD` — пароль БД
- `LDAP_*` — настройки Active Directory
- `WEB_CONCURRENCY` — число workers (рекомендуется 4–8)

## Ручной запуск

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Linux: source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## API

- Документация: http://127.0.0.1:8000/docs
- Health check: http://127.0.0.1:8000/api/health
- Список замечаний: `GET /api/remarks?page=1&page_size=50`
- Фоновый импорт: `POST /api/import/excel/async` → `GET /api/import/jobs/{id}`

## Структура проекта

```
backend/
  app/
    api/routers/   — маршруты API (auth, remarks, departments, ...)
    core/          — config, database, cache
    models/        — SQLAlchemy модели
    schemas/       — Pydantic схемы
    services/      — бизнес-логика, статистика, импорт
  main.py          — точка входа
  Dockerfile
  gunicorn.conf.py
frontend/
  src/             — React + TypeScript
  Dockerfile
docker-compose.yml
nginx/             — конфиг reverse proxy (в frontend/)
```

## Возможности

- Карточки замечаний с полями из Excel
- Назначение отделу и исполнителю
- Статусы: В работе → На рассмотрении → Устранено
- LDAP/AD авторизация
- Импорт из Excel (.xlsx)
- Фильтры и полнотекстовый поиск
- Роли: admin, gip, department_head, employee

# Back
cd "D:\!!!!1.БелНИПИ\Прога по змечаниям\backend"
.\venv\Scripts\python.exe -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Front
npm run dev 
