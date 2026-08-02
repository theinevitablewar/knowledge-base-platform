# Knowledge Base Platform

独立部署的多租户企业知识库与 RAG 管理平台。它提供文档上传、异步解析/分块/向量化、安全检索、流式问答、RBAC、审计日志，以及面向 LangGraph、Deep Agents 等调用方的 HTTP API。

## 功能

- React + Ant Design 管理后台：仪表盘、知识库、文档、Chunk、检索/问答测试、成员和任务中心。
- PDF、DOCX、TXT、Markdown 解析；LangChain 递归、分页和 Markdown 标题分块。
- Celery 异步幂等管线，原文件和解析中间件存 MinIO，业务数据存 PostgreSQL，向量存 Qdrant。
- JWT Access/Refresh Token、Argon2 密码、哈希 API Key、租户隔离和知识库五级 RBAC。
- SecureRetriever 强制安全过滤并用 PostgreSQL 二次校验；RAG 返回可验证 Chunk 引用。
- OpenAI-compatible LLM/Embedding、确定性 Mock 模式和可选 LangSmith tracing。

## 架构与目录

```text
backend/app/{api,models,schemas,repositories,services,permissions,rag,storage,workers}
backend/migrations/     Alembic 数据库迁移
backend/tests/          安全与领域回归测试
frontend/src/           React 管理后台
scripts/                Python SDK 与 Deep Agents Tool 示例
deploy/                 部署配置
```

详细边界和安全决策见 [docs/architecture.md](docs/architecture.md)。

## 环境要求

推荐 Docker Desktop（Compose v2）；本地开发需要 Python 3.12、[uv](https://docs.astral.sh/uv/) 和 Node.js 22。复制配置：

```powershell
Copy-Item .env.example .env
```

开发默认账号为 `admin / admin123456`。生产环境必须修改 `JWT_SECRET_KEY`、PostgreSQL/MinIO 密码和管理员密码。不要提交 `.env`。

### 模型与 LangSmith

无密钥时保留 `AI_MOCK_MODE=true`，系统不会调用付费模型。真实模式至少配置：

```env
AI_MOCK_MODE=false
OPENAI_API_KEY=...
OPENAI_BASE_URL=https://api.openai.com/v1
CHAT_MODEL=gpt-4.1-mini
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSION=1536
```

启用追踪时设置 `LANGSMITH_TRACING=true`、`LANGSMITH_API_KEY` 和 `LANGSMITH_PROJECT`。未提供 Key 时应用仍可启动。

## Docker Compose 启动

```powershell
docker compose up --build
```

后端容器会自动执行 `alembic upgrade head` 和幂等管理员初始化。服务地址：

- 管理后台：http://localhost:3000
- Swagger：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health
- MinIO Console：http://localhost:9001
- Qdrant Dashboard：http://localhost:6333/dashboard

停止服务使用 `docker compose down`；附加 `-v` 会永久删除开发数据卷，请谨慎使用。

## 本地开发

基础设施可先用 Compose 启动，再分别运行 API、Worker 和前端：

```powershell
docker compose up -d postgres redis minio minio-init qdrant
Set-Location backend
uv sync --all-groups
uv run alembic upgrade head
uv run python -m app.scripts.seed
uv run uvicorn app.main:app --reload

# 新终端
Set-Location backend
uv run celery -A app.workers.celery_app.celery_app worker --loglevel=INFO --pool=solo

# 新终端
Set-Location frontend
npm ci
npm run dev
```

迁移：`cd backend; uv run alembic upgrade head`。初始化管理员：`cd backend; uv run python -m app.scripts.seed`。

## API 示例

先登录并将返回的 Access Token 放入 `$token`：

```powershell
$login = Invoke-RestMethod -Method Post http://localhost:8000/api/v1/auth/login -ContentType 'application/json' -Body '{"username":"admin","password":"admin123456"}'
$token = $login.access_token
```

上传文档可在管理后台拖拽完成，也可使用 curl：

```powershell
curl.exe -H "Authorization: Bearer $token" -F "files=@policy.pdf" http://localhost:8000/api/v1/knowledge-bases/KB_ID/documents
```

安全检索：

```powershell
$body = @{query='预付款流程是什么？'; knowledge_base_ids=@('KB_ID'); top_k=8; score_threshold=0.2} | ConvertTo-Json
Invoke-RestMethod -Method Post http://localhost:8000/api/v1/retrieval/search -Headers @{Authorization="Bearer $token"} -ContentType 'application/json' -Body $body
```

问答使用相同请求体调用 `/api/v1/rag/answer`，流式 SSE 调用 `/api/v1/rag/answer/stream`。响应引用包含真实 `document_id`、`chunk_id`、页码和分数。

## Agent 接入

创建具有 `knowledge_base:read`、`document:read`、`retrieval:search`、`rag:answer` scopes 的 API Key，然后使用 `/api/v1/agent/*`。需要让外部应用上传、更新或删除文档时，再授予 `document:write`。异步客户端见 [scripts/knowledge_base_client.py](scripts/knowledge_base_client.py)，LangChain/Deep Agents `@tool` 示例见 [scripts/deep_agents_tool.py](scripts/deep_agents_tool.py)。Agent 不应直连 Qdrant、数据库或 MinIO。

## 权限模型

`owner` 可管理全部资源和设置；`admin` 可管理文档与成员；`editor` 可上传、编辑和重建索引；`contributor` 可查看、检索和上传；`viewer` 仅可查看与检索。服务端从认证上下文取得 `tenant_id`，忽略用户提供的租户过滤条件。可见范围为 `private`、`members`、`workspace`、`tenant`。

## 质量检查

```powershell
Set-Location backend
uv run pytest
uv run ruff check app tests
uv run mypy app

Set-Location ..\frontend
npm test
npm run lint
npm run typecheck
npm run build
```

也可使用 `make test`、`make lint`、`make format`。单元测试使用 SQLite、内存存储和确定性向量替身，不调用 OpenAI。

## 常见问题

- 文档一直 `queued`：检查 `worker` 日志和 Redis；Windows 本地 Worker 使用 `--pool=solo`。
- Embedding 维度错误：知识库配置、模型输出维度和 Qdrant Collection 必须一致；修改后重新索引。
- MinIO 上传失败：确认 bucket 初始化容器成功，且 endpoint 在容器内为 `minio:9000`。
- 无检索结果：文档必须为 `ready` 且 `enabled=true`，调用方也必须具有该知识库权限。

## 当前限制与路线图

MVP 仅实现稠密向量检索与四种文本格式；尚未实现 XLSX/PPTX/CSV/HTML、OCR、BM25/混合检索、RRF、Reranker、Query Rewrite、Parent Document Retrieval 和 Context Compression。后续将加入版本化 UI、批量任务操作、ABAC 策略引擎、评估数据集和生产级对象存储生命周期策略。
