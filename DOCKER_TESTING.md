# Docker testing runbook

## Requirements

- Docker Desktop
- Free local port `8080` or change `APP_PORT` in `.env`

## Start

```powershell
copy .env.docker.example .env
docker compose up -d --build
```

Open:

```text
http://localhost:8080
```

## Test users

If `.env` has `SEED_TEST_USERS=true`, the backend creates these users on first start.

Password for all test users:

```text
test123
```

Users:

- `admin` / `admin` - administrator
- `ogip` / `test123` - OGIP/GIP
- `pto_head` / `test123` - PТО department head
- `pto_emp1` / `test123` - PТО employee
- `pto_emp2` / `test123` - PТО employee
- `ot_head` / `test123` - ОТ department head
- `ot_emp1` / `test123` - ОТ employee
- `oe_head` / `test123` - ОЭ department head
- `oe_emp1` / `test123` - ОЭ employee

## Useful commands

```powershell
docker compose ps
docker compose logs -f backend
docker compose logs -f frontend
docker compose down
```

Reset test database and uploads:

```powershell
docker compose down -v
docker compose up -d --build
```
