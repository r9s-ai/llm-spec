---
name: llm-spec-audit-workflow
description: 在 llm-spec 仓库内实际执行 usage/billing 审计：跑用例生成 usage，查询 billing，再交给下游 skill 对账。
---

# LLM Spec Audit Workflow

用于需要完整走通 `usage -> billing -> audit` 的场景。若用户已经提供整理好的 usage 和 billing 数据，直接使用 `src/billing-audit/skills/usage-billing-match/SKILL.md`。

本 skill 只负责编排：

- billing 字段解释：`src/billing-audit/skills/r9s-billing-audit-workflow/skills/r9s-billing/SKILL.md`
- usage/billing 匹配判断：`src/billing-audit/skills/usage-billing-match/SKILL.md`

## Workflow

1. 运行 llm-spec audit 用例，生成 usage artifact。
2. 读取 usage artifact，取得 Unix 秒格式的 billing 查询时间窗口和 usage records。
3. 调用 `fetchBilling` 获取同一窗口内的 billing。
4. 读取 `r9s-billing` 理解 billing 字段。
5. 读取 `usage-billing-match` 完成审计判断与输出。

## Run Usage Cases

使用审计专用启动脚本生成 usage，不需要先 build。脚本默认值在 `scripts/run-audit-usage.sh` 内维护。脚本会自动定位到 `packages/llm-spec/` 目录，可从仓库任意位置执行：

```bash
bash src/billing-audit/skills/r9s-billing-audit-workflow/scripts/run-audit-usage.sh
```

## Usage Artifact

默认产物：

```text
src/billing-audit/data/usage.json
```

读取该文件作为 usage 证据来源。若不存在或没有可用记录，停止 workflow 并说明缺少 usage 证据。不要把 `requests.log` 当主 usage 来源；它只用于 debug 或补充证据。

## Fetch Billing

使用 `src/billing-audit/fetch-billing.ts` 查询 billing。时间窗口来自 usage artifact，`startTime` / `endTime` 必须是 Unix 秒格式。

可直接作为 CLI 执行：

```bash
pnpm dlx tsx src/billing-audit/fetch-billing.ts <startTime> <endTime>
```

或通过环境变量传参：

```bash
BILLING_START_TIME=1780970357 BILLING_END_TIME=1780970377 pnpm dlx tsx src/billing-audit/fetch-billing.ts
```

`url`、`bearerToken` 和 `user_id` 由 `fetchBilling` 自动从以下环境变量读取（通过 `loadDotEnvIfPresent()` 加载 `.env` 文件）：

- `BILLING_BASE_URL` — billing API 地址
- `BILLING_API_KEY` — bearer token
- `BILLING_USER_ID` — 可选；存在时会作为 `user_id` query 参数传给 billing API

查询成功后会保存：

```text
src/billing-audit/data/billing.json
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
