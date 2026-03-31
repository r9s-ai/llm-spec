# Claude Agent SDK Beta 功能和未测试参数分析

## 执行时间
2026-03-17

## 1. Beta 功能分析

### 当前支持的 Beta 功能

#### SDK 公开的 Beta 功能 (sdk.d.ts)
根据 SDK 类型定义 (`sdk.d.ts`),公开的 beta 功能:

```typescript
export declare type SdkBeta = 'context-1m-2025-08-07';
```

**`context-1m-2025-08-07`** - 启用 1M token 上下文窗口
- 仅适用于: Claude Sonnet 4/4.5 模型
- 官方文档: https://docs.anthropic.com/en/api/beta-headers

#### CLI 内部的 Beta 功能 (cli.js)
通过分析 cli.js 文件,发现 CLI 内部还有 **25 个** 其他 beta 功能,但这些功能**不在 SDK 公开 API 中**:

<details>
<summary>📋 点击查看完整的 CLI 内部 Beta 功能列表 (25个)</summary>

1. `vertex-2023-10-16` - Google Vertex AI 集成
2. `bedrock-2023-05-31` - AWS Bedrock 集成
3. `web-search-2025-03-05` - 网页搜索
4. `files-api-2025-04-14` - 文件 API
5. `oauth-2025-04-20` - OAuth 认证
6. `interleaved-thinking-2025-05-14` - 交错思考
7. `context-management-2025-06-27` - 上下文管理
8. `ccr-byoc-2025-07-29` - 自定义云资源
9. `environments-2025-11-01` - 环境管理
10. `token-counting-2024-11-01` - Token 计数优化
11. `message-batches-2024-09-24` - 批量消息处理
12. `skills-2025-10-02` - 技能系统
13. `tool-search-tool-2025-10-19` - 工具搜索
14. `tool-examples-2025-10-29` - 工具示例
15. `advanced-tool-use-2025-11-20` - 高级工具使用
16. `mcp-client-2025-11-20` - MCP 客户端
17. `effort-2025-11-24` - 输出努力级别
18. `structured-outputs-2025-11-13` - 结构化输出
19. `structured-outputs-2025-12-15` - 结构化输出(v2)
20. `mcp-servers-2025-12-04` - MCP 服务器
21. `compact-2026-01-12` - 上下文压缩
22. `prompt-caching-scope-2026-01-05` - Prompt 缓存作用域
23. `afk-mode-2026-01-31` - AFK 模式
24. `fast-mode-2026-02-01` - 快速模式
25. `redact-thinking-2026-02-12` - 思考内容脱敏

</details>

**重要**: 这些 CLI 内部 beta 功能不需要在 SDK 测试中覆盖,因为:
- ❌ 不在 `SDKSessionOptions.betas` 参数中
- ❌ 用户无法通过 SDK API 控制
- ✅ 可能通过其他机制(环境变量、配置)自动启用

### Beta 参数的使用方式

在 `SDKSessionOptions` 中:
```typescript
betas?: SdkBeta[];
```

在系统初始化消息 `SDKSystemMessage` 中会显示启用的 beta 功能:
```typescript
betas?: string[];
```

## 2. 现有测试覆盖情况

### 已有测试用例 (46个)
- 基础功能测试: 8个
- 增强测试: 38个

### Beta 相关测试
**当前状态**: ❌ **没有任何测试用例测试 `betas` 参数**

### CLAUDE_AGENT_PARAMS 覆盖的参数
```typescript
export const CLAUDE_AGENT_PARAMS = [
  'model',           // ✓ 已测试
  'prompt',          // ✓ 已测试
  'allowedTools',    // ✓ 已测试
  'disallowedTools', // ✓ 已测试
  'env',             // ✓ 已测试
  'streaming',       // ✓ 已测试
  'structured_output', // ✓ 已测试
] as const;
```

**缺少**: `betas` 参数未在列表中

## 3. 未测试的 SDKSessionOptions 参数

### 高优先级 (Beta 功能)
1. ❌ **`betas`** - Beta 功能启用
   - `context-1m-2025-08-07` - 1M 上下文窗口

### 中优先级 (核心功能)
2. ❌ **`canUseTool`** - 自定义权限处理器
3. ❌ **`continue`** - 继续最近的对话
4. ❌ **`cwd`** - 工作目录设置
5. ❌ **`tools`** - 工具集合配置 (preset 模式)
6. ❌ **`executableArgs`** - 可执行文件参数
7. ❌ **`extraArgs`** - 额外的 CLI 参数
8. ❌ **`fallbackModel`** - 回退模型
9. ❌ **`enableFileCheckpointing`** - 文件检查点
10. ❌ **`toolConfig`** - 工具配置
11. ❌ **`forkSession`** - 分叉会话

### 低优先级 (高级功能)
12. ❌ **`hooks`** - 钩子系统 (21种事件类型)
13. ❌ **`onElicitation`** - MCP 请求处理
14. ❌ **`persistSession`** - 会话持久化
15. ❌ **`includePartialMessages`** - 包含部分消息
16. ❌ **`thinking`** - 思考/推理行为控制

## 4. 需要添加的测试用例

### Beta 功能测试 (必需)

#### 4.1 基础 Beta 测试
- `beta_context_1m_basic` - 测试启用 1M 上下文窗口
- `beta_context_1m_with_session` - 在会话中使用 1M 上下文窗口
- `beta_context_1m_system_message` - 验证系统消息中显示 beta 功能
- `beta_invalid_feature` - 测试无效的 beta 功能错误处理

#### 4.2 Beta 功能与模型兼容性
- `beta_context_1m_sonnet` - Sonnet 4.6 + 1M 上下文
- `beta_context_1m_opus` - Opus 4.6 (应该不支持或忽略)
- `beta_context_1m_haiku` - Haiku 4.5 (应该不支持或忽略)

#### 4.3 Beta 功能边界测试
- `beta_multiple_features` - 测试多个 beta 功能 (未来扩展)
- `beta_empty_array` - 测试空 beta 数组
- `beta_with_large_context` - 使用大上下文测试

### 其他重要参数测试

#### 4.4 工作目录和会话管理
- `custom_cwd` - 自定义工作目录
- `continue_recent_conversation` - 继续最近的对话
- `fork_session` - 会话分叉测试
- `persist_session_false` - 禁用会话持久化

#### 4.5 工具配置
- `tools_preset_claude_code` - 使用 preset 工具集
- `tool_config_custom` - 自定义工具配置
- `enable_file_checkpointing` - 文件检查点功能

#### 4.6 可执行文件和参数
- `executable_args` - 可执行文件参数
- `extra_args` - 额外 CLI 参数
- `fallback_model` - 回退模型测试

#### 4.7 高级功能
- `thinking_adaptive` - 自适应思考模式
- `thinking_enabled` - 启用固定思考预算
- `thinking_disabled` - 禁用扩展思考
- `include_partial_messages` - 包含部分消息

## 5. Beta 功能启用条件

根据 SDK 文档,`context-1m-2025-08-07` beta 功能:

### 支持的模型
- ✅ Claude Sonnet 4
- ✅ Claude Sonnet 4.5
- ❓ Claude Opus 4.6 (需要测试验证)
- ❓ Claude Haiku 4.5 (需要测试验证)

### 启用方式
```typescript
const options: SDKSessionOptions = {
  model: 'claude-sonnet-4-6',
  betas: ['context-1m-2025-08-07'],
  // ... 其他选项
};
```

### 预期行为
1. 系统消息 (`SDKSystemMessage`) 应该包含 `betas: ['context-1m-2025-08-07']`
2. SDK 应该能够处理更大的上下文 (接近 1M tokens)
3. 不支持的模型应该忽略或返回错误

## 6. 测试策略

### Beta 功能测试原则
1. **验证启用**: 确认 beta 功能正确启用
2. **验证系统消息**: 检查 `SDKSystemMessage.betas` 字段
3. **模型兼容性**: 测试不同模型的兼容性
4. **错误处理**: 测试无效 beta 功能的处理
5. **功能验证**: 实际测试 beta 功能的效果

### 测试环境要求
- 需要有效的 API Key
- 需要支持 beta 功能的模型
- 可能需要更长的超时时间 (大上下文处理)

## 7. 下一步行动

1. ✅ 分析完成 - 识别所有 beta 功能和未测试参数
2. 🔄 编写测试用例 - 补充 beta 相关测试
3. ⏳ 运行测试 - 验证测试通过
4. ⏳ 更新文档 - 更新 README 和参数列表

## 8. 参考链接

- [Anthropic Beta Headers 文档](https://docs.anthropic.com/en/api/beta-headers)
- [Claude Agent SDK 类型定义](../node_modules/@anthropic-ai/claude-agent-sdk/sdk.d.ts)
- [现有测试用例](../src/api-sdk-tester/cases/anthropic/index.ts)
