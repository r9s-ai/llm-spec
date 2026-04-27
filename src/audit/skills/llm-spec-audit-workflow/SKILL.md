---
name: llm-spec-audit-workflow
description: 在 llm-spec 仓库内实际执行 usage/billing 审计：跑用例生成 usage，查询 billing，再交给下游 skill 对账。
---

# LLM Spec Audit Workflow

用于需要完整走通 `usage -> billing -> audit` 的场景。若用户已经提供整理好的 usage 和 billing 数据，直接使用 `src/audit/skills/usage-billing-match/SKILL.md`。

本 skill 只负责编排：

- billing 字段解释：`src/audit/skills/llm-spec-audit-workflow/skills/r9s-billing/SKILL.md`
- usage/billing 匹配判断：`src/audit/skills/usage-billing-match/SKILL.md`

## Workflow

1. 运行 llm-spec audit 用例，生成 usage artifact。
2. 读取 usage artifact，取得 Unix 秒格式的 billing 查询时间窗口和 usage records。
3. 调用 `fetchBilling` 获取同一窗口内的 billing。
4. 读取 `r9s-billing` 理解 billing 字段。
5. 读取 `usage-billing-match` 完成审计判断与输出。

## Run Usage Cases

使用审计专用启动脚本生成 usage，不需要先 build。脚本默认值在 `scripts/run-audit-usage.sh` 内维护：

```bash
bash src/audit/skills/llm-spec-audit-workflow/scripts/run-audit-usage.sh
```

## Usage Artifact

默认产物：

```text
src/audit/usage.json
```

读取该文件作为 usage 证据来源。若不存在或没有可用记录，停止 workflow 并说明缺少 usage 证据。不要把 `requests.log` 当主 usage 来源；它只用于 debug 或补充证据。

## Fetch Billing

使用 `src/audit/fetchBilling.ts` 查询 billing。时间窗口来自 usage artifact，`startTime` / `endTime` 必须是 Unix 秒格式。`url` 和 `bearerToken` 可由 `fetchBilling` 自动从环境变量读取。查询成功后会保存：

```text
src/audit/billing.json
```

不要输出 bearer token。缺少 billing url 或 bearer token 时，停止执行，说明错误。
## Audit

拿到 billing 后，先读取 `r9s-billing` 理解 billing 字段，再读取 `usage-billing-match` 执行匹配、比较、结论和输出。本 workflow 不定义审计规则或输出格式。

## Constraints

- 不要跳过 usage 证据收集直接审计。
- 严格按 Workflow 顺序执行，不要插入无关搜索、总结或额外分析。
- 不要输出与当前步骤无关的信息；需要输出时只报告必要路径、状态和阻塞原因。
- 不要在缺少 billing 配置时猜测或伪造。
- 不要泄露 secret。
- 不要在本 skill 中重复展开下游两个 skill 的完整规则。
