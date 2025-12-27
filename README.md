# Fairy
Fairy is a lightweight web agent that supports deep research capabilities.

## Installation

```bash
uv sync
```

## Web Demo (Next.js + FastAPI)

本仓库包含一个用于演示的 Web Demo（前后端分离），目录在：
- `apps/frontend`（Next.js）
- `apps/backend`（FastAPI）

### 1) 环境变量

- 后端：复制 `apps/backend/env.template` 为 `apps/backend/.env` 并填写：
  - `MODEL_BASE_URL` / `MODEL_API_KEY`
  - `TAVILY_API_KEY`
- 前端：复制 `apps/frontend/env.template` 为 `apps/frontend/.env.local`（默认后端地址 `http://localhost:8000`）

### 2) 启动后端（FastAPI）

后端会在本地创建 SQLite（默认路径：`apps/backend/var/fairy_demo.sqlite3`）。

```bash
cd apps/backend
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

### 3) 启动前端（Next.js）

```bash
cd apps/frontend
npm install
npm run dev
```

打开 `http://localhost:3000`，即可按流程演示：
用户意图 → 范围界定（必要时澄清）→ 研究简报 → 执行研究 → 最终报告。