## Fairy Demo Backend (FastAPI)

### 运行

1) 复制环境变量文件：

- 从 `env.template` 复制到 `.env` 并填写：
  - `MODEL_BASE_URL` / `MODEL_API_KEY`
  - `TAVILY_API_KEY`

2) 启动服务：

```bash
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

### 说明

- SSE：`GET /api/sessions/{session_id}/events`
- 会话状态：`GET /api/sessions/{session_id}`
- 写入用户消息并触发流水线：`POST /api/sessions/{session_id}/messages`


