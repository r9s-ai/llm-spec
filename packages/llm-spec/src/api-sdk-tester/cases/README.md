# Agent SDK 测试用例

本项目包含了针对两个Agent SDK的测试用例:

1. **@anthropic-ai/claude-agent-sdk** - Anthropic的Claude Agent SDK
2. **@openai/codex-sdk** - OpenAI的Codex SDK

## 测试用例结构

```
packages/llm-spec/src/
├── agents/
│   ├── claude-agent-provider.ts  # Claude Agent provider
│   └── codex-provider.ts         # Codex provider
└── api-sdk-tester/
    ├── environment/
    │   ├── runtime-config.ts     # 运行时环境与 provider 配置
    │   ├── case-filter.ts        # TARGET_CASES 过滤
    │   └── request-logging.ts    # 请求日志与 fetch 拦截
    ├── cases/
    │   ├── runtime.ts            # 用例执行器与摘要
    │   ├── types.ts              # TestCase 类型
    │   ├── anthropic/
    │   ├── openai/
    │   └── gemini/
    ├── runtime-config.ts         # 兼容导出层
    └── shared.ts                 # 兼容导出层
```

## 配置

### Claude Agent SDK

在`.env`文件中配置以下环境变量:

```bash
# API密钥 (必需) - 优先级从高到低
CLAUDE_AGENT_API_KEY=your_api_key_here
# 或复用Anthropic的API密钥
ANTHROPIC_API_KEY=your_anthropic_key_here
# 或使用通用的API密钥
API_KEY=your_generic_key

# API Base URL (可选) - 优先级从高到低
# 注意：API Base URL 通过环境变量 ANTHROPIC_API_BASE_URL 传递给 SDK
CLAUDE_AGENT_API_BASE_URL=https://your-custom-url.com
# 或复用Anthropic的Base URL
ANTHROPIC_API_BASE_URL=https://api.anthropic.com
# 或使用通用的Base URL
API_BASE_URL=https://api.example.com

# 其他环境变量配置
# 自定义 User-Agent 标识（推荐）
CLAUDE_AGENT_SDK_CLIENT_APP=my-app/1.0.0

# 自定义环境变量（SDK 会继承 process.env）
CUSTOM_VAR_1=value1
CUSTOM_VAR_2=value2

# 工作目录 (可选,默认为当前目录)
CLAUDE_AGENT_WORKING_DIRECTORY=/path/to/working/directory

# 是否跳过Git仓库检查 (可选,默认为true)
CLAUDE_AGENT_SKIP_GIT_REPO_CHECK=true

# 测试图片路径 (可选,用于图片输入测试)
CLAUDE_AGENT_TEST_IMAGE_PATH=/path/to/image.png

# 超时时间 (可选,默认45000ms)
CLAUDE_AGENT_TIMEOUT_MS=60000
```

### Codex SDK

在`.env`文件中配置以下环境变量:

```bash
# API密钥 (必需) - 优先级从高到低
CODEX_API_KEY=your_codex_key_here
# 或复用OpenAI的API密钥
OPENAI_API_KEY=your_openai_key_here
# 或使用通用的API密钥
API_KEY=your_generic_key

# API Base URL (可选) - 优先级从高到低
CODEX_API_BASE_URL=https://your-custom-url.com
# 或复用OpenAI的Base URL
OPENAI_API_BASE_URL=https://api.openai.com/v1
# 或使用通用的Base URL
API_BASE_URL=https://api.example.com

# 工作目录 (可选,默认为当前目录)
CODEX_WORKING_DIRECTORY=/path/to/working/directory

# 是否跳过Git仓库检查 (可选,默认为true)
CODEX_SKIP_GIT_REPO_CHECK=true

# 测试图片路径 (可选,用于图片输入测试)
CODEX_TEST_IMAGE_PATH=/path/to/image.png

# 超时时间 (可选,默认45000ms)
CODEX_TIMEOUT_MS=60000
```

### 环境变量复用说明

Agent SDK会自动复用对应平台的配置:

- **Claude Agent SDK** 会依次尝试:
  1. `CLAUDE_AGENT_API_KEY` → `ANTHROPIC_API_KEY` → `API_KEY`
  2. `CLAUDE_AGENT_API_BASE_URL` → `ANTHROPIC_API_BASE_URL` → `API_BASE_URL`

- **Codex SDK** 会依次尝试:
  1. `CODEX_API_KEY` → `OPENAI_API_KEY` → `API_KEY`
  2. `CODEX_API_BASE_URL` → `OPENAI_API_BASE_URL` → `API_BASE_URL`

这意味着如果你已经配置了 `OPENAI_API_KEY` 和 `OPENAI_API_BASE_URL`,Codex SDK会自动使用这些配置,无需额外设置。

## 运行测试

### 运行所有provider的测试

```bash
pnpm test:sdk
```

### 只运行特定的provider

设置环境变量`TARGET_PROVIDERS`:

```bash
# 只运行Claude Agent测试
TARGET_PROVIDERS=claude-agent pnpm test:sdk

# 只运行Codex测试
TARGET_PROVIDERS=codex pnpm test:sdk

# 运行多个provider
TARGET_PROVIDERS=claude-agent,codex pnpm test:sdk
```

## 测试用例说明

### Claude Agent SDK测试用例

#### 基础功能测试 (8个原有用例)

| 测试ID | 描述 | 覆盖参数 |
|--------|------|----------|
| `basic_prompt` | 基础单次prompt | model, prompt |
| `basic_session` | 创建并运行基础session | model, prompt |
| `streaming_session` | 流式session | model, prompt, streaming |
| `multi_turn_conversation` | 多轮对话 | model, prompt |
| `resume_session` | 恢复已存在的session | model, prompt |
| `allowed_tools` | 使用allowedTools配置 | model, prompt, allowedTools |
| `disallowed_tools` | 使用disallowedTools配置 | model, prompt, disallowedTools |
| `custom_env` | 使用自定义环境变量 | model, prompt, env |

#### 新增增强测试 (29个新增用例)

**模型和配置测试**:
| 测试ID | 描述 | 覆盖参数 |
|--------|------|----------|
| `different_model_opus` | 测试配置的 Opus 模型槽位 | model |
| `different_model_haiku` | 测试配置的 Haiku 模型槽位 | model |
| `custom_executable_node` | 自定义可执行文件：node | executable |

**权限模式测试**:
| 测试ID | 描述 | 覆盖参数 |
|--------|------|----------|
| `permission_mode_default` | 权限模式：默认模式 | permissionMode |
| `permission_mode_dont_ask` | 权限模式：dontAsk 模式 | permissionMode |
| `permission_mode_plan` | 权限模式：计划模式 | permissionMode |

**工具和结构化输出测试**:
| 测试ID | 描述 | 覆盖参数 |
|--------|------|----------|
| `tool_combination` | 同时使用 allowedTools 和 disallowedTools | allowedTools, disallowedTools |
| `tool_execution_with_session` | 会话中工具执行测试 | allowedTools |
| `multiple_tools_different_types` | 多种不同类型工具 | allowedTools |
| `tool_use_summary` | 工具使用摘要消息 | allowedTools |
| `structured_output_json` | 测试结构化输出 JSON 格式 | structured_output |

**会话管理测试**:
| 测试ID | 描述 | 覆盖参数 |
|--------|------|----------|
| `long_running_session` | 长时间运行的会话（5轮） | - |
| `session_error_recovery` | 会话错误恢复测试 | - |
| `multiple_concurrent_sessions` | 多个并发会话测试 | - |
| `session_without_close` | 资源自动清理测试 | - |
| `session_closure_cleanup` | 会话资源清理 | - |
| `session_id_persistence` | SessionId 持久化测试 | - |
| `session_uuid_tracking` | Session UUID 跟踪 | - |

**消息类型和流式测试**:
| 测试ID | 描述 | 覆盖参数 |
|--------|------|----------|
| `system_message_analysis` | 系统初始化消息分析 | - |
| `assistant_message_streaming` | 助手消息流式传输 | streaming |
| `streaming_message_types` | 流式消息类型分析 | streaming |
| `result_message_metadata` | 结果消息元数据分析 | - |

**错误处理和边界测试**:
| 测试ID | 描述 | 覆盖参数 |
|--------|------|----------|
| `error_handling_invalid_model` | 错误处理：无效模型名称 | model |
| `error_during_execution_handling` | 执行期间错误处理 | - |
| `empty_and_special_prompts` | 边界情况：空提示和特殊字符 | prompt |
| `large_prompt_handling` | 大型提示处理 | prompt |

**环境和高级功能测试**:
| 测试ID | 描述 | 覆盖参数 |
|--------|------|----------|
| `env_custom_api_key` | 自定义 API 密钥环境变量 | env |
| `prompt_with_context` | 带上下文的复杂提示 | prompt |

**API Base URL 和环境变量测试** (9个新增):
| 测试ID | 描述 | 覆盖参数 |
|--------|------|----------|
| `custom_api_base_url` | 自定义 API Base URL | env |
| `env_var_interpolation` | 环境变量插值测试 | env |
| `api_key_from_env` | 从环境变量读取 API Key | env |
| `user_agent_customization` | User-Agent 自定义标识 | env |
| `multiple_env_vars` | 多个环境变量组合测试 | env |
| `api_base_url_with_session` | 会话中使用自定义 API Base URL | env, allowedTools |
| `invalid_api_base_url` | 测试无效的 API Base URL 错误处理 | env |
| `api_base_url_priority` | API Base URL 环境变量优先级测试 | env |
| `env_inheritance` | 环境变量继承测试 | env |

**Beta 功能测试** (23个静态用例；另有 26 个 `beta_catalog_*` 目录覆盖用例):
| 测试ID | 描述 | 覆盖参数 |
|--------|------|----------|
| `beta_context_1m_basic` | Beta: 启用 1M 上下文窗口 | betas, model, prompt |
| `beta_context_1m_with_session` | Beta: 在会话中使用 1M 上下文窗口 | betas, model, prompt, streaming |
| `beta_context_1m_system_message` | Beta: 验证系统消息中显示 beta 功能 | betas, model, prompt |
| `beta_context_1m_opus` | Beta: Opus 模型槽位与 1M 上下文 (兼容性测试) | betas, model, prompt |
| `beta_context_1m_haiku` | Beta: Haiku 模型槽位与 1M 上下文 (兼容性测试) | betas, model, prompt |
| `beta_invalid_feature` | Beta: 测试无效的 beta 功能错误处理 | betas, model, prompt |
| `beta_empty_array` | Beta: 测试空 beta 数组 | betas, model, prompt |
| `beta_with_tools` | Beta: Beta 功能与工具组合测试 | betas, model, prompt, allowedTools |
| `beta_context_1m_streaming` | Beta: 1M 上下文窗口流式传输测试 | betas, model, prompt, streaming |
| `beta_context_1m_multi_turn` | Beta: 1M 上下文窗口多轮对话测试 | betas, model, prompt |
| `beta_context_1m_resume_session` | Beta: 恢复使用 1M 上下文的会话 | betas, model, prompt |
| `beta_context_1m_with_custom_env` | Beta: 1M 上下文与自定义环境变量组合 | betas, model, prompt, betas, env |
| `beta_context_1m_error_recovery` | Beta: 1M 上下文会话错误恢复 | betas, model, prompt |
| `beta_thinking_adaptive` | Beta: Adaptive thinking (触发 interleaved-thinking beta) | model, prompt, thinking |
| `beta_thinking_enabled` | Beta: Enabled thinking (固定 token 预算) | model, prompt, thinking |
| `beta_thinking_disabled` | Beta: Disabled thinking | model, prompt, thinking |
| `beta_effort_low` | Beta: Effort=low (触发 effort beta) | model, prompt, effort |
| `beta_effort_high` | Beta: Effort=high | model, prompt, effort |
| `beta_effort_max` | Beta: Effort=max | model, prompt, effort |
| `beta_effort_with_thinking` | Beta: Effort + Thinking 组合 | model, prompt, effort, thinking |
| `beta_mcp_servers_config` | Beta: MCP 服务器配置 (触发 mcp beta) | model, prompt, mcpServers |
| `beta_context_1m_with_effort` | Beta: 1M 上下文 + Effort 组合 | betas, model, prompt, effort |
| `beta_thinking_effort_context_1m` | Beta: Thinking + Effort + 1M 三重组合 | betas, model, prompt, thinking, effort |

**总计**: 68个 Claude Agent 测试用例 (42个静态用例 + 26个 `beta_catalog_*` 目录覆盖用例)

## Beta 功能触发说明

### 通过 SDK 参数触发的 Beta 功能

虽然 CLI 内部有 26 个 beta 功能,但只有部分可以通过 SDK 参数触发:

#### 1. 显式启用的 Beta 功能
- **`context-1m-2025-08-07`** - 通过 `betas: ['context-1m-2025-08-07']` 参数启用

#### 2. Thinking 相关 Beta 功能
- **`interleaved-thinking-2025-05-14`** - 通过 `thinking: { type: 'adaptive' }` 或 `thinking: { type: 'enabled' }` 自动触发
- **`redact-thinking-2026-02-12`** - 可能与 thinking 配置相关

#### 3. Effort 相关 Beta 功能
- **`effort-2025-11-24`** - 通过 `effort: 'low' | 'medium' | 'high' | 'max'` 参数自动触发

#### 4. MCP 相关 Beta 功能
- **`mcp-client-2025-11-20`** - 通过 `mcpServers` 配置自动触发
- **`mcp-servers-2025-12-04`** - 通过 `mcpServers` 配置自动触发

#### 5. 上下文管理 Beta 功能
- **`context-management-2025-06-27`** - 系统自动启用
- **`compact-2026-01-12`** - 系统自动启用

#### 6. 其他内部 Beta 功能
其余 19 个 beta 功能是 CLI 内部实现细节,无法通过 SDK 参数直接控制。

### 测试策略

- ✅ **显式测试**: 测试用户可控的 beta 功能 (`betas` 参数)
- ✅ **触发测试**: 测试通过其他参数自动触发的 beta 功能
- ✅ **组合测试**: 测试多个 beta 功能的组合使用
- ℹ️ **观察测试**: 验证系统消息中的 beta 功能列表

### Codex SDK测试用例

| 测试ID | 描述 | 覆盖参数 |
|--------|------|----------|
| `basic_thread` | 创建并运行基础thread | model, prompt, workingDirectory |
| `basic_thread_streaming` | 创建并运行基础thread (streaming) | model, prompt, workingDirectory, streaming |
| `structured_output` | 使用structured output输出JSON | model, prompt, outputSchema |
| `structured_output_streaming` | 使用structured output输出JSON (streaming) | model, prompt, outputSchema, streaming |
| `multi_turn_conversation` | 多轮对话 | model, prompt |
| `image_input` | 图片输入测试 | model, prompt |
| `resume_thread` | 恢复已存在的thread | model, prompt |
| `config_override` | 使用config覆盖 | model, config |
| `env_control` | 控制环境变量 | model, env |
| `abort_signal` | 使用AbortSignal取消操作 | model, prompt |
| `thread_events` | 监听thread事件 | model, prompt, streaming |
| `usage_tracking` | 追踪token使用情况 | model, prompt |

## 测试报告

测试完成后,可以生成HTML、JSON和文本格式的报告:

```bash
REPORT_FILE=./reports/agent-test-report pnpm test:sdk
```

这将生成:
- `./reports/agent-test-report` (JSON格式)
- `./reports/agent-test-report.html` (HTML格式)
- `./reports/agent-test-report.txt` (文本格式)

## 注意事项

1. **API密钥安全**: 请勿将API密钥提交到版本控制系统
2. **工作目录**: Agent SDK需要在有效的Git仓库中运行,除非设置`skipGitRepoCheck=true`
3. **超时设置**: Agent操作可能需要较长时间,建议设置适当的超时时间
4. **并发限制**: 由于Agent操作可能消耗较多资源,建议避免并发运行大量测试

## 扩展测试用例

要添加新的测试用例,请在相应的`cases/`目录下编辑`index.ts`文件:

```typescript
const cases = defineCases({
  'my_test_case': {
    description: '我的测试用例描述',
    covers: ['param1', 'param2'],
    precondition: () => {
      // 可选: 返回undefined表示条件满足,返回字符串表示跳过原因
      return undefined;
    },
    run: async () => {
      // 测试逻辑
      // 返回测试结果字符串
      return 'test result';
    },
  },
});
```

## 故障排除

### 常见问题

1. **API密钥错误**: 确保环境变量已正确设置
2. **工作目录错误**: 确保工作目录存在且有适当的权限
3. **超时错误**: 增加超时时间设置
4. **Git仓库检查失败**: 设置`skipGitRepoCheck=true`或确保在Git仓库中运行

### 调试模式

要查看详细的请求和响应日志,可以查看测试输出中的日志信息。

## Claude Agent SDK 特性分析

### 核心 API

#### 1. 单次提示 API
```typescript
unstable_v2_prompt(message: string, options: SDKSessionOptions): Promise<SDKResultMessage>
```
- 一次性提示，无需管理会话
- 返回 `SDKResultSuccess | SDKResultError`

#### 2. 会话管理 API
```typescript
// 创建新会话
unstable_v2_createSession(options: SDKSessionOptions): SDKSession

// 恢复现有会话
unstable_v2_resumeSession(sessionId: string, options: SDKSessionOptions): SDKSession
```

#### 3. SDKSession 方法
```typescript
session.send(message: string): Promise<void>
session.stream(): AsyncIterable<SDKMessage>
session.close(): void
session.sessionId: string
```

### SDKSessionOptions 配置选项

#### 基础配置
- `model` (string) - 模型名称，支持 claude-4.x 系列
- `env` (Record<string, string>) - 环境变量
- `executable` ('node' | 'bun') - 可执行文件类型
- `executableArgs` (string[]) - 可执行文件参数
- `pathToClaudeCodeExecutable` (string) - Claude Code 可执行文件路径

#### 工具控制
- `allowedTools` (string[]) - 自动允许的工具列表
- `disallowedTools` (string[]) - 禁用的工具列表
- `canUseTool` (CanUseTool) - 自定义权限处理器

#### 权限模式
- `permissionMode` (PermissionMode) - 权限模式:
  - `'default'` - 标准权限行为
  - `'acceptEdits'` - 自动接受文件编辑
  - `'bypassPermissions'` - 绕过所有权限检查（需要 allowDangerouslySkipPermissions）
  - `'plan'` - 计划模式，不执行工具
  - `'dontAsk'` - 不提示权限

#### 高级特性
- `hooks` - 事件钩子系统（21种事件类型）
- `plugins` - 插件系统
- `promptSuggestions` - 启用提示建议
- `agentProgressSummaries` - Agent 进度摘要

### 消息类型

SDK 流式响应包含多种消息类型：

- `SDKResultMessage` - 最终结果（成功或错误）
- `SDKSystemMessage` - 系统初始化消息
- `SDKAssistantMessage` - 助手响应
- `SDKPartialAssistantMessage` - 流式事件
- `SDKToolProgressMessage` - 工具进度
- `SDKToolUseSummaryMessage` - 工具使用摘要
- `SDKStatusMessage` - 状态更新
- `SDKTaskStartedMessage` - 任务开始
- `SDKTaskProgressMessage` - 任务进度
- `SDKTaskNotificationMessage` - 任务通知
- 以及更多...

### 结果消息类型

#### SDKResultSuccess
```typescript
{
  type: 'result';
  subtype: 'success';
  duration_ms: number;
  duration_api_ms: number;
  num_turns: number;
  result: string;
  total_cost_usd: number;
  usage: NonNullableUsage;
  structured_output?: unknown;
}
```

#### SDKResultError
```typescript
{
  type: 'result';
  subtype: 'error_during_execution'
       | 'error_max_turns'
       | 'error_max_budget_usd'
       | 'error_max_structured_output_retries';
  errors: string[];
}
```

### Hook 事件类型

SDK 支持 21 种 hook 事件：

- `PreToolUse` - 工具使用前
- `PostToolUse` - 工具使用后
- `PostToolUseFailure` - 工具使用失败后
- `UserPromptSubmit` - 用户提交提示
- `SessionStart` - 会话开始
- `SessionEnd` - 会话结束
- `SubagentStart` / `SubagentStop` - 子 agent 生命周期
- `PermissionRequest` - 权限请求
- `TaskCompleted` - 任务完成
- 以及更多...

### Beta 特性说明

**所有 API 都使用 `unstable_v2_` 前缀**，表示：
- 实验性功能，API 可能随时更改
- 不建议在生产环境中直接使用
- 需要充分的错误处理和测试

### 最佳实践

#### 1. 会话管理
```typescript
const session = unstable_v2_createSession(options);
try {
  await session.send('message');
  for await (const msg of session.stream()) {
    // 处理消息
  }
} finally {
  session.close(); // 始终关闭会话
}
```

#### 2. 错误处理
```typescript
const result = await unstable_v2_prompt(msg, options);
if (result.type === 'result') {
  if (result.subtype === 'success') {
    console.log(result.result);
  } else {
    // 处理错误: error_during_execution, error_max_turns, etc.
    console.error(result.errors);
  }
}
```

#### 3. 工具控制
```typescript
const options: SDKSessionOptions = {
  model: process.env.CLAUDE_AGENT_MODEL,
  allowedTools: ['Read', 'Glob'],  // 只允许这些工具
  disallowedTools: ['Bash'],       // 明确禁用这些工具
};
```

#### 4. 环境变量配置
```typescript
const options: SDKSessionOptions = {
  model: process.env.CLAUDE_AGENT_MODEL,
  env: {
    ...process.env,
    ANTHROPIC_API_KEY: apiKey,
    CLAUDE_AGENT_SDK_CLIENT_APP: 'my-app/1.0.0',
  },
};
```

### 测试覆盖统计

- **总测试用例数**: 68个
- **参数覆盖率**: 9/13 (69%)
- **Beta 特性覆盖**: 高
- **错误场景覆盖**: 良好
- **边界情况覆盖**: 良好

### 未测试的高级特性

以下特性需要额外的测试用例：

1. **Hooks 系统** - 所有 21 种 hook 事件
2. **插件系统** - 本地和远程插件加载
3. **自定义权限处理器** - `canUseTool` 回调
4. **高级权限模式** - `acceptEdits` 和 `bypassPermissions`
5. **提示建议** - `promptSuggestions` 功能
6. **Agent 进度摘要** - `agentProgressSummaries` 功能

详细信息请参考 [SDK 类型定义文件](../../../node_modules/@anthropic-ai/claude-agent-sdk/sdk.d.ts)。

## API Base URL 和环境变量特性

### API Base URL 配置

Claude Agent SDK 通过环境变量来配置 API Base URL，#### 环境变量优先级

SDK 使用以下优先级顺序读取 API Base URL：

1. `ANTHROPIC_API_BASE_URL` (推荐)
2. `API_BASE_URL` (通用)

**注意**：虽然配置文件支持 `CLAUDE_AGENT_API_BASE_URL`，但 SDK 内部统一使用 `ANTHROPIC_API_BASE_URL`。

#### 使用场景

1. **代理服务器** - 通过自定义 Base URL 使用代理服务器
2. **测试环境** - 使用本地测试服务器
3. **企业部署** - 连接到内部 API 网关
4. **区域端点** - 使用特定区域的 API 端点

#### 示例配置

```bash
# 使用代理服务器
ANTHROPIC_API_BASE_URL=https://proxy.company.com/anthropic

# 使用测试环境
ANTHROPIC_API_BASE_URL=http://localhost:8080

# 企业内部网关
ANTHROPIC_API_BASE_URL=https://api-gateway.internal.company.com
```

### 环境变量传递

#### 环境变量继承

SDK 默认继承 `process.env` 中的所有环境变量：

```typescript
const options: SDKSessionOptions = {
  model: process.env.CLAUDE_AGENT_MODEL,
  env: {
    ...process.env,  // 继承所有环境变量
    ANTHROPIC_API_KEY: apiKey,
  },
};
```

#### 自定义环境变量

可以添加任意自定义环境变量：

```typescript
const options: SDKSessionOptions = {
  model: process.env.CLAUDE_AGENT_MODEL,
  env: {
    ...process.env,
    ANTHROPIC_API_KEY: apiKey,
    CUSTOM_CONFIG_VAR: 'custom_value',
    DEBUG_MODE: 'true',
  },
};
```

#### User-Agent 自定义

通过 `CLAUDE_AGENT_SDK_CLIENT_APP` 环境变量自定义 User-Agent 标识：

```typescript
const options: SDKSessionOptions = {
  model: process.env.CLAUDE_AGENT_MODEL,
  env: {
    ...process.env,
    ANTHROPIC_API_KEY: apiKey,
    CLAUDE_AGENT_SDK_CLIENT_APP: 'my-app/1.0.0',
  },
};
```

### 测试覆盖

我们添加了 **9 个测试用例** 专门测试 API Base URL 和环境变量相关特性：

1. ✅ **custom_api_base_url** - 测试自定义 API Base URL
2. ✅ **env_var_interpolation** - 测试环境变量插值功能
3. ✅ **api_key_from_env** - 测试从环境变量读取 API Key
4. ✅ **user_agent_customization** - 测试 User-Agent 自定义标识
5. ✅ **multiple_env_vars** - 测试多个环境变量组合使用
6. ✅ **api_base_url_with_session** - 测试在会话中使用自定义 API Base URL
7. ✅ **invalid_api_base_url** - 测试无效 URL 的错误处理
8. ✅ **api_base_url_priority** - 测试环境变量优先级
9. ✅ **env_inheritance** - 测试环境变量继承行为

### API Base URL 相关错误处理

SDK 会自动处理以下错误：

- **网络错误** - 无法连接到指定的 Base URL
- **DNS 解析失败** - URL 域名无法解析
- **SSL/TLS 错误** - HTTPS 证书验证失败
- **超时错误** - 连接或请求超时

错误会通过 `SDKResultError` 返回，包含详细的错误信息。
