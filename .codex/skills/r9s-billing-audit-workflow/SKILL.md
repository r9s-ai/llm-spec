---
name: r9s-billing-audit-workflow
description: 当用户要求在本仓库执行 llm-spec 的 R9S billing 审计流程、生成 usage artifact、拉取 billing 记录，或对比 usage 和 billing 时使用。
---

# R9S Billing 审计流程

当本 skill 触发时，执行仓库内定义的 workflow：

```text
packages/llm-spec/src/billing-audit/skills/r9s-billing-audit-workflow/SKILL.md
```

先读取该文件，并以它作为唯一事实来源执行。除非 workflow 里给出更具体的路径，否则其中的相对路径都从 `packages/llm-spec` 解析。

不要用临时步骤替代 workflow。特别注意：

- 先生成 usage 证据，再拉取 billing。
- 使用 workflow 中指定的 usage artifact 和 billing artifact 路径。
- 不要泄露 bearer token 或其他 secret。
- 如果缺少 billing 配置，停止执行并说明缺少的配置。
- 使用中文回答。
