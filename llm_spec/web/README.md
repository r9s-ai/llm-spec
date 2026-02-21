# llm-spec Web Backend

A FastAPI-based web API for managing and executing llm-spec test suites.

## 环境要求

- Python >= 3.11
- PostgreSQL >= 14
- Node.js >= 18 (前端开发)
- pnpm >= 9 (前端包管理器)
- uv (Python 包管理器)

## 快速开始

### 1. 安装依赖

```bash
# 安装 Python 依赖 (包含 web 扩展)
uv sync --extra dev --extra web

# 安装前端依赖
cd frontend && pnpm install && cd ..
```

### 2. 配置数据库

#### 创建 PostgreSQL 数据库

```bash
# 创建数据库
createdb llm_spec

# 或者使用 psql
psql -U postgres -c "CREATE DATABASE llm_spec;"
```

#### 初始化数据库表结构

```bash
# 方式1: 全新安装
psql -U postgres -d llm_spec -f llm_spec/web/schema.sql

# 方式2: 从旧版本升级（保留现有数据）
psql -U postgres -d llm_spec -f llm_spec/web/migrations/001_add_run_batch.sql
```

### 3. 配置环境变量

创建 `.env` 文件（或直接导出环境变量）：

```bash
# 复制示例配置
cp llm_spec/web/env.example .env

# 编辑配置
```

环境变量说明：

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `LLM_SPEC_WEB_DATABASE_URL` | PostgreSQL 连接字符串 | `postgresql+psycopg://postgres:postgres@localhost:5432/llm_spec` |
| `LLM_SPEC_WEB_APP_TOML_PATH` | llm-spec.toml 配置文件路径 | `llm-spec.toml` |
| `LLM_SPEC_WEB_MOCK_MODE` | 是否使用 Mock 模式 | `false` |
| `LLM_SPEC_WEB_MOCK_BASE_DIR` | Mock 数据目录 | `tests/integration/mocks` |
| `LLM_SPEC_WEB_CORS_ORIGINS` | CORS 允许的源 | `["*"]` |

### 4. 配置 Provider

创建 `llm-spec.toml` 配置文件，配置 API Provider：

```toml
[openai]
api_key = "sk-xxx"
base_url = "https://api.openai.com/v1"

[anthropic]
api_key = "sk-xxx"
base_url = "https://api.anthropic.com"
```

### 5. 导入测试套件

将现有的测试套件导入数据库：

```bash
uv run python scripts/migrate_suites_to_web.py \
  --database-url 'postgresql+psycopg://postgres:postgres@localhost:5432/llm_spec' \
  --config llm-spec.toml \
  --suites suites
```

### 6. 启动服务

#### 启动后端服务

```bash
# 方式1: 作为模块运行 (推荐)
uv run python -m llm_spec.web.main

# 方式2: 使用 uvicorn
uv run uvicorn llm_spec.web.main:app --reload --port 8000
```

后端服务将在 `http://localhost:8000` 启动。

#### 启动前端服务

```bash
cd frontend
pnpm dev
```

前端服务将在 `http://localhost:5173` 启动。

## 数据库表结构

### suite - 测试套件

| 字段 | 类型 | 说明 |
|------|------|------|
| id | varchar(36) | 主键 UUID |
| provider | varchar(32) | Provider 名称 (openai, anthropic, gemini, xai) |
| endpoint | varchar(255) | API 端点路径 |
| name | varchar(255) | 套件名称 |
| status | varchar(16) | 状态 (active/archived) |
| latest_version | integer | 最新版本号 |
| created_at | timestamptz | 创建时间 |
| updated_at | timestamptz | 更新时间 |

### suite_version - 套件版本

| 字段 | 类型 | 说明 |
|------|------|------|
| id | varchar(36) | 主键 UUID |
| suite_id | varchar(36) | 外键关联 suite |
| version | integer | 版本号 |
| raw_json5 | text | 原始 JSON5 内容 |
| parsed_json | jsonb | 解析后的 JSON 数据 |
| created_by | varchar(128) | 创建者 |
| created_at | timestamptz | 创建时间 |

### run_batch - 测试任务批次

| 字段 | 类型 | 说明 |
|------|------|------|
| id | varchar(36) | 主键 UUID |
| status | varchar(16) | 状态 (running/completed/cancelled) |
| mode | varchar(16) | 执行模式 (real/mock) |
| total_runs | integer | 总运行数 |
| completed_runs | integer | 已完成数 |
| passed_runs | integer | 通过数 |
| failed_runs | integer | 失败数 |
| started_at | timestamptz | 开始时间 |
| finished_at | timestamptz | 结束时间 |
| created_at | timestamptz | 创建时间 |

### run_job - 执行任务

| 字段 | 类型 | 说明 |
|------|------|------|
| id | varchar(36) | 主键 UUID |
| status | varchar(16) | 状态 (queued/running/success/failed/cancelled) |
| mode | varchar(16) | 执行模式 (real/mock) |
| provider | varchar(32) | Provider 名称 |
| endpoint | varchar(255) | API 端点 |
| batch_id | varchar(36) | 外键关联 run_batch |
| suite_version_id | varchar(36) | 外键关联 suite_version |
| config_snapshot | jsonb | 配置快照 |
| started_at | timestamptz | 开始时间 |
| finished_at | timestamptz | 结束时间 |
| progress_total | integer | 总测试数 |
| progress_done | integer | 已完成数 |
| progress_passed | integer | 通过数 |
| progress_failed | integer | 失败数 |
| error_message | text | 错误信息 |

### run_result - 执行结果

| 字段 | 类型 | 说明 |
|------|------|------|
| run_id | varchar(36) | 主键，外键关联 run_job |
| run_result_json | jsonb | 完整结果 JSON 数据 |
| created_at | timestamptz | 创建时间 |

### run_test_result - 单个测试结果

| 字段 | 类型 | 说明 |
|------|------|------|
| id | varchar(36) | 主键 UUID |
| run_id | varchar(36) | 外键关联 run_job |
| test_id | varchar(512) | 测试 ID |
| test_name | varchar(255) | 测试名称 |
| parameter_name | varchar(255) | 参数名 |
| parameter_value | jsonb | 参数值 |
| status | varchar(16) | 状态 (pass/fail) |
| fail_stage | varchar(32) | 失败阶段 |
| reason_code | varchar(64) | 失败原因码 |
| latency_ms | integer | 延迟毫秒 |
| raw_record | jsonb | 原始记录 |

## API 接口

### 健康检查
- `GET /healthz` - 健康检查

### 测试套件管理
- `GET /api/suites` - 列出所有套件
- `POST /api/suites` - 创建套件
- `GET /api/suites/{suite_id}` - 获取套件详情
- `PUT /api/suites/{suite_id}` - 更新套件
- `DELETE /api/suites/{suite_id}` - 删除套件
- `GET /api/suites/{suite_id}/versions` - 列出版本
- `POST /api/suites/{suite_id}/versions` - 创建新版本
- `GET /api/suite-versions/{version_id}` - 获取版本详情

### Provider 配置
- `GET /api/provider-configs` - 列出所有 Provider 配置
- `GET /api/provider-configs/{provider}` - 获取单个 Provider 配置
- `PUT /api/provider-configs/{provider}` - 更新 Provider 配置

### 批次管理
- `POST /api/batches` - 创建批次（多个路由同时执行）
- `GET /api/batches` - 列出批次
- `GET /api/batches/{batch_id}` - 获取批次详情（含运行列表）
- `DELETE /api/batches/{batch_id}` - 删除批次及其运行
- `GET /api/batches/{batch_id}/runs` - 获取批次下的运行列表

### 执行管理
- `POST /api/runs` - 创建并启动单个执行任务
- `GET /api/runs` - 列出执行任务
- `GET /api/runs/{run_id}` - 获取执行详情
- `POST /api/runs/{run_id}/cancel` - 取消执行
- `GET /api/runs/{run_id}/events` - 获取执行事件 (轮询)
- `GET /api/runs/{run_id}/events/stream` - SSE 事件流
- `GET /api/runs/{run_id}/result` - 获取执行结果
- `GET /api/runs/{run_id}/tests` - 获取测试结果列表

### 设置
- `GET /api/settings/toml` - 获取 TOML 配置
- `PUT /api/settings/toml` - 更新 TOML 配置

## 架构说明

```
llm_spec/web/
├── api/                    # API 路由层 (Controller)
│   ├── deps.py            # 依赖注入
│   ├── suites.py          # 套件路由
│   ├── runs.py            # 执行路由
│   ├── batches.py         # 批次路由
│   ├── provider_configs.py # Provider 配置路由
│   └── settings.py        # 设置路由
│
├── core/                   # 核心功能
│   ├── db.py              # 数据库连接
│   ├── exceptions.py      # 自定义异常
│   ├── error_handler.py   # 全局异常处理
│   └── utils.py           # 工具函数
│
├── models/                 # SQLAlchemy ORM 模型
│   ├── suite.py           # Suite, SuiteVersion
│   ├── run.py             # RunBatch, RunJob, RunEvent, RunResult, RunTestResult
│   └── provider.py        # ProviderConfigModel
│
├── schemas/                # Pydantic 请求/响应模型
│   ├── suite.py
│   ├── run.py
│   ├── provider.py
│   └── settings.py
│
├── services/               # 业务逻辑层
│   ├── suite_service.py
│   ├── run_service.py
│   └── provider_service.py
│
├── repositories/           # 数据访问层
│   ├── suite_repo.py
│   ├── run_repo.py
│   └── provider_repo.py
│
├── adapters/               # 适配器
│   └── mock_adapter.py    # Mock 适配器
│
├── main.py                 # FastAPI 应用入口
├── config.py               # 配置管理
├── schema.sql              # 数据库表结构
└── openapi.yaml            # OpenAPI 规范
```

## 错误处理

所有错误使用统一格式：

```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Suite not found: abc123"
  }
}
```

错误码说明：
- `NOT_FOUND` (404): 资源不存在
- `VALIDATION_ERROR` (400): 输入数据无效
- `DUPLICATE` (409): 资源已存在
- `CONFIGURATION_ERROR` (500): 配置问题
- `EXECUTION_ERROR` (500): 执行失败

## 开发说明

### 运行测试

```bash
uv run pytest
```

### 代码格式化

```bash
uv run ruff format .
uv run ruff check . --fix
```

### 类型检查

```bash
uv run pyright
```

## Mock 模式

Mock 模式用于测试时不实际调用 API：

```bash
export LLM_SPEC_WEB_MOCK_MODE=true
```

Mock 数据存放在 `tests/integration/mocks/` 目录下。
