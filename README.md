# 标书 AI Harness Agent

> 面向技术标的 AI 撰写工作台，具备证据追溯与人工审核能力。

## 项目状态

设计完成，正在实现中。

## 文档

- 开发文档：[开发文档](./docs/开发文档.md)
- API 文档：[API文档](./docs/API文档.md)
- 数据库文档：[数据库模型](./docs/数据库模型.md)

## 技术栈

- 后端：Python 3.12、FastAPI、PostgreSQL、Redis、Celery、LangGraph、Milvus
- 前端：React、TypeScript、Vite 部署：Docker Compose、Nginx

## 代码检查、测试

```bash
Set-Location backend
uv run ruff check --fix app tests
uv run ruff format app tests
uv run ruff format --check app tests
uv run mypy app
uv run python -m pytest -q
```

## 本地启动

- Docker

```bash
docker compose --env-file ./backend/.env -f ./backend/deploy/compose.yaml up -d
docker compose --env-file ./backend/.env -f ./backend/deploy/compose.yaml ps
docker compose --env-file ./backend/.env -f ./backend/deploy/compose.yaml logs postgres
```

- 后端

```bash
Set-Location backend
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

