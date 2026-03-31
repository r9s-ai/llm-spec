# Beta 功能触发条件映射表

## 分析方法
通过分析 sdk.d.ts 和 cli.js,识别出哪些 SDK 参数会触发 CLI 内部的 beta 功能。

## 映射关系

### 1. Thinking 相关 Beta 功能

#### 触发参数
```typescript
thinking?: ThinkingConfig;
effort?: 'low' | 'medium' | 'high' | 'max';
```

#### 触发的 Beta 功能
- ✅ `interleaved-thinking-2025-05-14` - 交错思考
- ✅ `redact-thinking-2026-02-12` - 思考内容脱敏

#### 触发条件
- 当设置 `thinking` 参数时
- 当设置 `effort` 参数时
- 在 Opus 4.6 上默认使用 adaptive thinking

### 2. MCP (Model Context Protocol) 相关 Beta 功能

#### 触发参数
```typescript
mcpServers?: Record<string, McpServerConfig>;
```

#### 触发的 Beta 功能
- ✅ `mcp-client-2025-11-20` - MCP 客户端
- ✅ `mcp-servers-2025-12-04` - MCP 服务器

#### 触发条件
- 当配置 `mcpServers` 参数时
- 当启动 MCP 服务器时

### 3. Context Management 相关 Beta 功能

#### 触发的 Beta 功能
- ✅ `context-management-2025-06-27` - 上下文管理
- ✅ `compact-2026-01-12` - 上下文压缩

#### 触发条件
- 当会话上下文过长需要压缩时
- 系统自动触发上下文管理

### 4. Effort 相关 Beta 功能

#### 触发参数
```typescript
effort?: 'low' | 'medium' | 'high' | 'max';
```

#### 触发的 Beta 功能
- ✅ `effort-2025-11-24` - 输出努力级别

#### 触发条件
- 当设置 `effort` 参数时

### 5. Structured Outputs 相关 Beta 功能

#### 触发的 Beta 功能
- ✅ `structured-outputs-2025-11-13` - 结构化输出
- ✅ `structured-outputs-2025-12-15` - 结构化输出(v2)

#### 触发条件
- 当使用结构化输出功能时
- 可能与 `outputSchema` 相关

### 6. 其他 Beta 功能 (未找到触发条件)

以下 beta 功能在 CLI 内部使用,但未找到明确的 SDK 参数触发条件:

- `advanced-tool-use-2025-11-20` - 高级工具使用
- `web-search-2025-03-05` - 网页搜索
- `files-api-2025-04-14` - 文件 API
- `token-counting-2024-11-01` - Token 计数优化
- `message-batches-2024-09-24` - 批量消息处理
- `prompt-caching-scope-2026-01-05` - Prompt 缓存作用域
- `afk-mode-2026-01-31` - AFK 模式
- `skills-2025-10-02` - 技能系统
- `tool-search-tool-2025-10-19` - 工具搜索
- `tool-examples-2025-10-29` - 工具示例

## 测试策略

### 可测试的 Beta 功能 (有明确的触发条件)

1. **Thinking 相关** - 通过设置 `thinking` 和 `effort` 参数触发
2. **MCP 相关** - 通过配置 `mcpServers` 参数触发

### 不可测试的 Beta 功能 (无明确触发条件或自动启用)

1. **Context Management** - 系统自动触发
2. **Structured Outputs** - 未找到明确的 SDK 参数
3. **其他功能** - 内部实现细节

## 测试用例编写计划

### 优先级 1: Thinking 相关 Beta 功能
- `beta_thinking_adaptive` - 测试 adaptive thinking 模式
- `beta_thinking_enabled` - 测试 enabled thinking 模式
- `beta_effort_low` - 测试 effort='low'
- `beta_effort_high` - 测试 effort='high'
- `beta_effort_max` - 测试 effort='max'

### 优先级 2: MCP 相关 Beta 功能
- `beta_mcp_servers` - 测试 MCP 服务器配置
- `beta_mcp_client` - 测试 MCP 客户端

### 优先级 3: 上下文管理 (观察性测试)
- `beta_context_management_observation` - 观察上下文管理行为

## 实现注意事项

1. **系统消息验证**: 检查 `SDKSystemMessage.betas` 数组中是否包含预期的 beta 功能
2. **功能验证**: 验证 beta 功能是否正确工作
3. **兼容性**: 测试不同模型的兼容性
4. **错误处理**: 测试无效配置的处理

## 结论

- **可测试**: 6个 beta 功能 (thinking 相关 2个, MCP 相关 2个, effort 1个, context management 1个)
- **不可测试**: 19个 beta 功能 (无明确触发条件或内部实现)
- **测试策略**: 重点测试有明确 SDK 参数触发的 beta 功能
