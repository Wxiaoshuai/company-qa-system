# company-qa-system

公司问答系统，基于实用的 RAG 基线（FastAPI + 本地向量索引 + 可选 LlamaIndex 加速），并支持内部员工登录与页面/API 权限控制。

## 项目结构

```text
company-qa-system/
  app/
    api/routes.py
    core/config.py
    models/schemas.py
    services/qa_service.py
    main.py
  data/
    docs/                # Put your source docs here (.txt/.md/.markdown)
    vector_store/        # Generated index.json after ingestion
  scripts/
    ingest.py
  .env.example
  .gitignore
  requirements.txt
  requirements-llamaindex.txt
```

## 环境搭建

1. 创建虚拟环境并安装依赖

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

可选 LlamaIndex 增强：

```powershell
pip install -r requirements-llamaindex.txt
```

2. 配置环境变量

```powershell
Copy-Item .env.example .env
```

`.env` 中需要设置：

- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`（可选，支持兼容 OpenAI 的网关）

可选的 RAG 配置：

- `RAG_ENGINE=auto`
- `RAG_LLAMAINDEX_PERSIST_DIR=data/vector_store/llamaindex`

3. 将文档放入 `data/docs/` 目录（UTF-8 `.txt` / `.md`）

4. 构建向量索引

```powershell
python scripts/ingest.py
```

如果安装了可选的 LlamaIndex 依赖，同样的命令还会持久化 LlamaIndex 索引。

5. 启动 API

```powershell
uvicorn app.main:app --reload --port 8000
```

可选的管理员初始化：

```powershell
python scripts/init_admin.py
```

## API

- 登录页面：`GET /login`
- 聊天界面：`GET /`
- 管理页面：`GET /admin`
- 健康检查：`GET /health`
- 提问接口：`POST /api/v1/qa/ask`
- 流式接口：`POST /api/v1/qa/stream`
- 登录接口：`POST /api/v1/auth/login`
- 登出接口：`POST /api/v1/auth/logout`
- 当前用户：`GET /api/v1/auth/me`

请求体：

```json
{
  "question": "What is our annual leave policy?"
}
```

响应体：

```json
{
  "answer": "...",
  "references": [
    "data/docs/hr_policy.md#3",
    "data/docs/employee_handbook.md#7"
  ]
}
```

测试：
```powershell
python -c "import requests; response = requests.post('http://127.0.0.1:8000/api/v1/qa/ask', json={'question': 'What is the annual leave policy?'}); print(response.json())"
```

打开聊天页面：
```text
http://127.0.0.1:8000/
```

聊天页面：

- 可在桌面浏览器和移动 H5 浏览器上使用
- 访问前需要登录
- 包含欢迎问题快捷方式，便于快速启动
- 通过浏览器 `localStorage` 存储聊天记录
- 服务器端逐步推送答案
- 在折叠区域显示响应引用

管理页面：

- 仅 `admin` 用户可访问
- 支持创建用户、启用/禁用账户、重置密码、分配角色

## 注意事项

- 项目支持两个 RAG 后端：
  - 原生 JSON 向量检索，以获得最大兼容性
  - 可选的 LlamaIndex 查询引擎，在 `RAG_ENGINE=auto` 时自动优先使用
- 业务 API 现在通过 HttpOnly cookie 会话要求认证访问。
- 生产环境建议改用向量数据库存储索引，并补充认证、日志和评估功能。

## 部署

- 阿里云 ECS 部署指南：`DEPLOY_ALIYUN.md`
