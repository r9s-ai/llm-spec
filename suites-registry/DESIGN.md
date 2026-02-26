# suites-registry 结构设计

> 本文档描述 `suites-registry` 的目录结构、文件格式和 `llm-spec.toml` 配置设计，
> 目标是让社区能够方便地添加多个渠道（channel）的多个路由（route）的多个模型（model）的测试用例。

---

## 目录结构

```
suites-registry/
├── DESIGN.md                                # 本文档
├── CONTRIBUTING.md
├── README.md
├── providers/
│   ├── openai/                              # 原始 provider，自有完整路由定义
│   │   ├── provider.toml
│   │   ├── routes/
│   │   │   ├── chat_completions.json5       # 路由测试模板
│   │   │   ├── embeddings.json5
│   │   │   ├── images_generations.json5
│   │   │   ├── audio_speech.json5
│   │   │   └── responses.json5
│   │   └── models/
│   │       ├── gpt-4o-mini.toml             # ⭐ 社区维护
│   │       ├── gpt-4o.toml
│   │       ├── gpt-4.1.toml
│   │       ├── o3-mini.toml
│   │       └── gpt-5.1-codex.toml
│   ├── anthropic/
│   │   ├── provider.toml
│   │   ├── routes/
│   │   │   └── messages.json5
│   │   └── models/
│   │       ├── claude-haiku-4.5.toml
│   │       ├── claude-sonnet-4.toml
│   │       └── claude-opus-4.toml
│   ├── gemini/
│   │   ├── provider.toml
│   │   ├── routes/
│   │   │   ├── generate_content.json5
│   │   │   └── stream_generate_content.json5
│   │   └── models/
│   │       ├── gemini-3-flash-preview.toml
│   │       └── gemini-2.5-pro.toml
│   ├── xai/                                 # OpenAI 兼容，继承路由
│   │   ├── provider.toml                    # routes_from = "openai"
│   │   ├── routes/                          # 空！路由从 openai 继承
│   │   └── models/
│   │       └── grok-beta.toml
│   └── deepseek/                            # ⭐ 社区新增 provider 示例
│       ├── provider.toml                    # routes_from = "openai"
│       ├── routes/                          # 空，或放 deepseek 独有路由
│       └── models/
│           ├── deepseek-chat.toml
│           ├── deepseek-coder.toml
│           └── deepseek-reasoner.toml
├── assets/                                   # 公共测试资源（图片、音频等）
│   ├── images/
│   └── audio/
├── scripts/
    ├── validate.py                           # 校验所有文件格式
    └── generate_suites.py                    # 组合 route × model → SpecTestSuite
```

**设计原则**：学习 [models.dev](https://github.com/poe-platform/models.dev) 的思路——用目录结构 + 简单文件表达数据，社区只需添加/修改文件即可贡献，无需改代码。

| 层级 | 职责 | 格式 | 谁维护 |
|------|------|------|--------|
| **provider** | 定义一个 API 规范 + 认证方式 | `provider.toml` | 项目核心 |
| **route** | 定义一个路由的测试模板 | `routes/{route}.json5` | 项目核心 + 社区 |
| **model** | 定义一个模型的元信息和路由覆盖 | `models/{model-id}.toml` | ⭐ 社区 |

---

## 各文件格式

### 1. `provider.toml` — Provider 元信息与 Header 配置

```toml
name = "OpenAI"

# ────────────────────────────────────────────
# api_family: 决定使用哪种 HTTP adapter 行为
#   - "openai"    → Authorization: Bearer {api_key}
#   - "anthropic" → x-api-key: {api_key} + anthropic-version header
#   - "gemini"    → x-goog-api-key: {api_key}, 模型名在 URL 中
# ────────────────────────────────────────────
api_family = "openai"

# 文档链接
doc = "https://platform.openai.com/docs/api-reference"

# ────────────────────────────────────────────
# routes_from: 路由继承（可选）
# 从另一个 provider 继承路由定义，避免重复复制 routes/ 文件
# 适用于 OpenAI 兼容类 provider（xAI、DeepSeek、Groq、Together AI 等）
# 本 provider routes/ 下的同名文件会覆盖继承的路由
# ────────────────────────────────────────────
# routes_from = "openai"

# 自定义请求头（可选）
# 所有请求都会携带这些 header，会覆盖 adapter 默认 header
# 这使得不同 provider 的 header 差异完全可配置，无需硬编码 adapter 类
[headers]
# 示例: Anthropic 的版本头
# anthropic-version = "2023-06-01"
# 示例: 某些中转渠道需要的额外头
# x-custom-provider = "openai"
```

**DeepSeek 的 `provider.toml` 示例**（OpenAI 兼容 provider）：

```toml
name = "DeepSeek"
api_family = "openai"
doc = "https://platform.deepseek.com/api-docs"

# ⭐ 继承 openai 的路由定义，无需重写 routes/
routes_from = "openai"
```

> **关于 Header 差异**：
>
> 分析现有 4 个 adapter，它们的区别 **只有** header：
>
> | Provider | Auth Header | 额外 Header |
> |----------|-------------|-------------|
> | OpenAI | `Authorization: Bearer {key}` | 无 |
> | xAI | `Authorization: Bearer {key}` | 无（与 OpenAI 完全相同） |
> | Anthropic | `x-api-key: {key}` | `anthropic-version: 2023-06-01` |
> | Gemini | `x-goog-api-key: {key}` | 无 |
>
> 通过 `api_family`(决定 auth 方式) + `[headers]`(可选额外 header) 的组合，
> 可以完全配置化处理所有中转渠道，无需为每个渠道写新的 adapter 类。

---

### 2. `routes/{route}.json5` — 路由测试模板

**与当前 suite JSON5 格式高度兼容**，核心变化：
- 移除 `provider` 字段（由目录结构决定）
- 移除 `base_params` 中的 `model` 字段（由 model 文件注入）

```json5
{
  // 路由路径
  endpoint: "/v1/chat/completions",

  // Schema 引用（指向内置 Python schema 名）
  schemas: {
    response: "openai.ChatCompletionResponse",
    stream_chunk: "openai.ChatCompletionChunkResponse",
  },

  // 基线参数（不含 model，model 由框架自动注入）
  base_params: {
    messages: [
      { role: "user", content: "Say hello" },
    ],
  },

  // 流式规则
  stream_rules: {
    min_observations: 2,
    checks: [
      { type: "required_terminal", value: "[DONE]" },
    ],
  },

  // 测试用例（与现有格式 100% 兼容，新增 tags 可选字段）
  tests: [
    { name: "test_baseline", is_baseline: true, tags: ["core"] },
    {
      name: "test_param_temperature",
      params: { temperature: 0.7 },
      test_param: { name: "temperature", value: 0.7 },
      tags: ["core"],
    },
    {
      name: "test_param_logprobs",
      params: { logprobs: true, top_logprobs: 3 },
      test_param: { name: "logprobs", value: true },
      tags: ["rare"],
    },
    {
      name: "test_tool_call",
      params: { tools: [/* ... */] },
      test_param: { name: "tools", value: [/* ... */] },
      tags: ["expensive", "tool_use"],
    },
    // ...其他测试与现有完全一致
  ],
}
```

**预定义 Tags**（建议但不强制）：

| Tag | 含义 | 用途 |
|-----|------|------|
| `core` | 核心/高频参数 | 快速回归测试 |
| `expensive` | 消耗大量 token 或耗时长 | 避免不必要的花费 |
| `rare` | 低频使用的参数 | 完整测试时才跑 |
| `streaming` | 涉及 streaming 的测试 | 单独测试流式能力 |
| `multimodal` | 涉及图片/音频/视频 | 多模态能力测试 |
| `tool_use` | 涉及 function calling / tools | 工具调用测试 |
| `safety` | 安全/内容过滤相关 | 安全合规测试 |

> Tags 自由定义，不做硬性限制。以上为推荐标签，社区可以添加自定义 tag。

**Gemini 的特殊处理**：Gemini 的 endpoint 中包含模型名（`/v1beta/models/{model}:generateContent`），
框架会根据 `api_family = "gemini"` 自动将 `{model}` 占位符替换为实际模型 ID，
而不是注入到 body 参数中。route 文件中的 `endpoint` 使用 `{model}` 占位符：

```json5
{
  // Gemini: 模型名在 URL 中，用 {model} 占位
  endpoint: "/v1beta/models/{model}:generateContent",
  // ...
}
```

---

### 3. `models/{model-id}.toml` — 模型定义 ⭐ 社区核心贡献点

模型的 `id` 自动从文件名推导（与 models.dev 一致），无需在文件内重复。

#### 最简示例

```toml
# models/gpt-4o-mini.toml
name = "GPT-4o mini"
routes = ["chat_completions", "embeddings"]
```

社区贡献者只需创建一个 `.toml` 文件，填写 `name` 和 `routes` 就可以完成最基础的贡献。

#### 完整示例

```toml
# models/gpt-4o-mini.toml
name = "GPT-4o mini"

# 该模型支持哪些路由（引用 routes/ 下的文件名，不含扩展名）
routes = ["chat_completions", "embeddings"]

# 跳过该模型不支持的测试
skip_tests = [
  "test_param_reasoning_effort",   # 仅 o 系列支持
  "test_param_modalities",         # 仅 audio 模型支持
  "test_role_developer",           # 仅 o1+ 支持
]
```

#### 高级示例：需要覆盖基线参数的模型

```toml
# models/o3-mini.toml
name = "o3 mini"
routes = ["chat_completions"]

# 覆盖该模型的基线参数（o 系列需要 max_completion_tokens 代替 max_tokens）
[base_params_override]
max_completion_tokens = 1024

skip_tests = [
  "test_param_temperature",        # o 系列不支持 temperature
  "test_param_top_p",
  "test_param_logit_bias",
]
```

#### 高级示例：添加额外测试

```toml
# models/gpt-5.1-codex.toml
name = "GPT-5.1 Codex"
routes = ["chat_completions", "responses"]

# 模型特有功能的额外测试
[[extra_tests]]
route = "chat_completions"
name = "test_param_reasoning_effort_codex"
description = "Test reasoning_effort for codex model"
[extra_tests.params]
reasoning_effort = "high"
max_completion_tokens = 2048
[extra_tests.test_param]
name = "reasoning_effort"
value = "high"
```

---

## Provider 扩展策略

社区新增 provider 时，根据场景不同，工作量差异很大：

| 场景 | 社区需要做什么 | 工作量 |
|------|--------------|--------|
| **OpenAI 兼容 provider**（xAI、DeepSeek、Groq、Together AI、SiliconFlow…） | 创建 `provider.toml`（设 `routes_from = "openai"`）+ 添加 `models/*.toml` | ⭐ 极低 |
| **已有 provider + 独有路由**（如 Mistral 的 FIM 补全） | 继承已有路由 + 在 `routes/` 下添加独有路由 JSON5 | 低 |
| **全新 API 规范 provider** | 完整写 `provider.toml` + `routes/*.json5` + `models/*.toml` | 中等 |

### 路由继承机制 (`routes_from`)

大量 provider 兼容 OpenAI API 格式，它们使用相同的 `/v1/chat/completions` 路由、相同的请求/响应 schema、相同的 streaming 格式。为避免重复复制路由文件，`provider.toml` 支持 `routes_from` 字段：

```toml
# providers/deepseek/provider.toml
name = "DeepSeek"
api_family = "openai"
routes_from = "openai"     # ← 继承 openai 的路由定义
```

继承后的目录只需要 `provider.toml` + `models/`：

```
providers/deepseek/
├── provider.toml          # routes_from = "openai"
├── routes/                # 可以为空，或放 deepseek 独有路由
└── models/                # ⭐ 社区只需添加模型文件
    ├── deepseek-chat.toml
    ├── deepseek-coder.toml
    └── deepseek-reasoner.toml
```

**加载优先级**：本 provider `routes/` 下的同名文件 > `routes_from` 继承的路由。
这意味着如果 deepseek 的 `/v1/chat/completions` 行为有差异，可以在 `routes/chat_completions.json5` 中覆盖。

### 递归继承

`routes_from` 继承是 **递归的**——继承的是目标 provider **完整解析后的路由集**，包含它自身从上游继承的路由和它自己补充的路由。社区补充的 routes 同样可以被下游 provider 继承。

**示例**：Mistral 在 OpenAI 基础上补充了 FIM 路由，另一个 provider 再继承 Mistral：

```
openai/routes/           → {chat_completions, embeddings, images_generations, ...}

mistral/provider.toml    → routes_from = "openai"
mistral/routes/          → {fim_completions}              ← mistral 独有
mistral 解析后路由集      = {chat_completions, embeddings, ..., fim_completions}

some-cloud/provider.toml → routes_from = "mistral"        ← 继承 mistral 的全部
some-cloud 解析后路由集   = {chat_completions, embeddings, ..., fim_completions}
```

解析过程：

1. 解析 `some-cloud` → `routes_from = "mistral"` → 先递归解析 mistral
2. 解析 `mistral` → `routes_from = "openai"` → 先解析 openai
3. openai 的 routes/: `{chat_completions, embeddings, ...}`
4. 合并 mistral 本地 routes/: + `{fim_completions}`
5. mistral 完整路由集: `{chat_completions, embeddings, ..., fim_completions}`
6. some-cloud 继承 mistral 完整路由集
7. 合并 some-cloud 自己的 routes/（本地覆盖优先）

### 循环继承检测

框架在递归解析 `routes_from` 时 **必须检测循环引用**，避免死循环。实现方式：解析时维护一个 visited set，遇到重复即报错退出。

```
# 错误示例：A → B → A 形成循环
provider-a/provider.toml  →  routes_from = "provider-b"
provider-b/provider.toml  →  routes_from = "provider-a"

# 框架应输出清晰的错误信息：
# Error: Circular routes_from detected: provider-a → provider-b → provider-a
```

### 社区添加新 provider 示例

**场景 1：添加 Groq（OpenAI 兼容）**

```bash
# 1. 创建 provider 目录
mkdir -p suites-registry/providers/groq/{routes,models}

# 2. 创建 provider.toml
cat > suites-registry/providers/groq/provider.toml << 'EOF'
name = "Groq"
api_family = "openai"
doc = "https://console.groq.com/docs/api-reference"
routes_from = "openai"
EOF

# 3. 添加模型
cat > suites-registry/providers/groq/models/llama-3.3-70b.toml << 'EOF'
name = "Llama 3.3 70B"
routes = ["chat_completions"]
skip_tests = ["test_param_logit_bias", "test_param_service_tier"]
EOF

# 完成！提交 PR 即可
```

**场景 2：添加 Mistral（OpenAI 兼容 + 独有 FIM 路由）**

```bash
mkdir -p suites-registry/providers/mistral/{routes,models}

# provider.toml 继承 openai 路由
cat > suites-registry/providers/mistral/provider.toml << 'EOF'
name = "Mistral"
api_family = "openai"
doc = "https://docs.mistral.ai/api"
routes_from = "openai"
EOF

# 添加 Mistral 独有的 FIM 路由（不在 openai 中）
cat > suites-registry/providers/mistral/routes/fim_completions.json5 << 'EOF'
{
  endpoint: "/v1/fim/completions",
  schemas: { response: "openai.ChatCompletionResponse" },
  base_params: {
    prompt: "def fibonacci(n):",
    suffix: "    return result",
  },
  tests: [
    { name: "test_baseline", is_baseline: true },
  ],
}
EOF

# 添加模型
cat > suites-registry/providers/mistral/models/codestral-latest.toml << 'EOF'
name = "Codestral"
routes = ["chat_completions", "fim_completions"]
EOF
```

## 测试资源 (Assets) 管理

对于涉及文件上传的测试（如多模态模型、语音识别），测试资源统一存放在 `assets/` 目录下。

### 目录规范

1.  **公共资源**：存放在 `suites-registry/assets/`，供所有 provider 复用（如标准测试音频 `hello_en.mp3`）。
2.  **Provider 特定资源**：存放在 `suites-registry/providers/{provider}/assets/`（可选，适用于该厂商特有的测试文件）。

### 引用方式

在 `routes/*.json5` 或 `models/*.toml` 中，使用**相对于 registry 根目录**的路径：

```json5
// routes/audio_transcriptions.json5
{
  tests: [
    {
      name: "test_baseline",
      files: {
        file: "assets/audio/hello_en.mp3", // 指向 suites-registry/assets/audio/hello_en.mp3
      }
    }
  ]
}
```

**加载逻辑说明**：
Runner 会尝试按以下优先级解析相对路径：
1.  相对于当前配置文件（route/model）的路径。
2.  递归向上查找父级目录（直到 registry 根目录）。
3.  相对于 `suites-registry/` 根目录。

---

## 运行时组合逻辑

框架加载 suites-registry 时，将 **route × model** 做笛卡尔积展开：

```
providers/openai/routes/chat_completions.json5
    × providers/openai/models/gpt-4o-mini.toml    → SpecTestSuite(provider=openai, model=gpt-4o-mini)
    × providers/openai/models/gpt-4o.toml          → SpecTestSuite(provider=openai, model=gpt-4o)
    × providers/openai/models/o3-mini.toml         → SpecTestSuite(provider=openai, model=o3-mini, skip=[temp,top_p,...])

providers/openai/routes/chat_completions.json5   ← 通过 routes_from 继承
    × providers/deepseek/models/deepseek-chat.toml → SpecTestSuite(provider=deepseek, model=deepseek-chat)
```

对每个组合：
1. 解析 `routes_from`，合并继承路由和本地路由（本地优先）
2. 加载 route 文件的 `base_params`、`tests`、`schemas`、`stream_rules`
3. 注入 model name 到 `base_params.model`（或 Gemini 的 URL 占位符）
4. 应用 model 的 `base_params_override`
5. 过滤掉 model 的 `skip_tests`
6. 追加 model 的 `extra_tests`
7. 生成最终的 `SpecTestSuite`

---

## 配置文件 `llm-spec.toml` 设计

### 向后兼容模式（当前格式）

```toml
# 旧格式完全兼容，行为不变
[openai]
api_key = "sk-..."
base_url = "https://api.openai.com"
timeout = 30.0
```

### 新格式：providers 模式

```toml
[log]
enabled = true
level = "INFO"

[report]
output_dir = "./reports"

[providers.openai]
api_key = "sk-..."
base_url = "https://api.openai.com"
timeout = 30.0

[providers.anthropic]
api_key = "sk-ant-..."
base_url = "https://api.anthropic.com"
timeout = 30.0
```

### 新格式：channel 模式（中转渠道）

核心场景：**一个中转 API 同时提供多个 provider 的路由，共用同一对 api_key + base_url**。

```toml
[log]
enabled = true
level = "INFO"

[report]
output_dir = "./reports"

# ─────────────────────────────────────────────
# Channel: 一个中转渠道，一对 key+url 覆盖多个 provider
# ─────────────────────────────────────────────
[[channels]]
name = "huamedia"
description = "华媒体中转站"
api_key = "sk-xxx"
base_url = "https://api.huamedia.tv"
timeout = 300.0

  # 该渠道支持的 providers 及其路由和模型
  [[channels.providers]]
  name = "openai"
  routes = ["chat_completions", "embeddings"]
  models = ["gpt-4o-mini", "gpt-4o", "gpt-4.1"]

  [[channels.providers]]
  name = "anthropic"
  routes = ["messages"]
  models = ["claude-haiku-4.5", "claude-sonnet-4"]

  [[channels.providers]]
  name = "gemini"
  routes = ["generate_content"]
  models = ["gemini-3-flash-preview"]

# 也可以同时配置直连
[[channels]]
name = "openai-official"
description = "OpenAI 官方直连"
api_key = "sk-official"
base_url = "https://api.openai.com"
timeout = 30.0

  [[channels.providers]]
  name = "openai"
  routes = ["chat_completions", "responses"]
  models = ["gpt-4o-mini", "o3-mini"]
```

### 配置解析逻辑

```
llm-spec.toml 加载
    │
    ├─ 旧格式 (顶层 [openai] / [anthropic])
    │   → 为每个 provider 生成一个默认 channel
    │   → 使用 registry 中该 provider 的所有 route × 所有 model
    │
    ├─ providers 格式 ([providers.openai])
    │   → 同旧格式，但结构更清晰
    │
    └─ channels 格式 ([[channels]])
        → 严格按配置展开：只运行 channel 中列出的 provider/route/model
```

---

## CLI 设计

```bash
# 运行所有
uv run python -m llm_spec run

# 按 provider 过滤
uv run python -m llm_spec run --provider openai

# 按 channel 过滤（channel 模式下）
uv run python -m llm_spec run --channel huamedia

# 按模型过滤
uv run python -m llm_spec run --model gpt-4o-mini

# 按路由过滤
uv run python -m llm_spec run -k "chat_completions"

# 按 tag 过滤（只跑核心测试）
uv run python -m llm_spec run --tags core

# 排除昂贵测试
uv run python -m llm_spec run --exclude-tags expensive

# 组合过滤
uv run python -m llm_spec run --channel huamedia --provider openai --model gpt-4o-mini --tags core

# 校验 registry 文件格式
uv run python -m llm_spec validate
```

---

## Schema 治理策略

**Schema 定义在 Python 代码中（`packages/core/src/llm_spec/validation/schemas/`），由项目核心团队维护。**

route 文件通过名称引用已有 schema（如 `"openai.ChatCompletionResponse"`），社区贡献者只需从可用列表中选择，无需自行定义。

不开放社区自定义 schema 的理由：

1. **中转渠道不会改变 Schema**：中转渠道只是代理请求，响应结构与原始 provider 完全一致
2. **LLM API 生态高度趋同**：绝大多数 provider 走 OpenAI 兼容协议，`openai.*` schema 即可覆盖。Anthropic 和 Gemini 是仅有的两个独立规范，均已有 schema
3. **Schema 决定测试正确性**：错误的 schema 会导致所有基于它的测试结果失效，需要对 API 规范有深入理解的维护者

**可用 Schema 清单**（route 文件中的 `schemas` 字段可选值）：

| Schema 名称 | 适用场景 |
|------------|----------|
| `openai.ChatCompletionResponse` | OpenAI 及所有兼容渠道的 chat/completions |
| `openai.ChatCompletionChunkResponse` | OpenAI 及兼容渠道的 streaming chunk |
| `anthropic.MessagesResponse` | Anthropic Messages API |
| `anthropic.AnthropicStreamChunk` | Anthropic streaming chunk |
| `gemini.GenerateContentResponse` | Gemini GenerateContent API |

> 如需新增 schema（如支持全新 API 规范的 provider），需通过 PR 提交到 `packages/core/src/llm_spec/validation/schemas/`，由核心团队 review 后合入。

**社区可以贡献的部分**：

| 可社区贡献   | 说明 |
|-------------|------|
| `models/*.toml` | 模型支持的路由、跳过的测试、额外测试 |
| route 文件中的 `required_fields` | 某模型新增了 response 字段 |
| route 文件中的新测试用例 | 新参数的测试探针 |
| 新的 `provider.toml` | 新增一个 provider（如 DeepSeek、Groq） |

---

## 实施阶段

### Phase 1: 目录结构迁移

- 现有 `openai/chat_completions.json5` → 移到 `openai/routes/chat_completions.json5`
- 创建各 `provider.toml`
- 创建基础 `models/*.toml`
- CLI 兼容层：同时扫描旧路径和新 `routes/` 路径

### Phase 2: route × model 组合加载

- 实现 `load_provider_registry()` 函数
- 实现 route × model 笛卡尔积展开
- model 的 `skip_tests` / `extra_tests` / `base_params_override` 生效

### Phase 3: Channel 配置与 Header 配置化

- 扩展 `llm-spec.toml` 解析器支持 `[[channels]]`
- `provider.toml` 中的 `[headers]` 配置注入 adapter
- CLI 新增 `--channel` / `--model` 过滤参数
- 报告支持 channel 维度聚合
