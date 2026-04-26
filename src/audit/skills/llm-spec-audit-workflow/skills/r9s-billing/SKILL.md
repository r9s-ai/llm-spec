---
name: r9s-billing
description: 当用户需要理解 R9S billing 接口响应结构，尤其是 data.list 中单条计费记录及 ext 中的多模态和工具计费扩展字段时使用。
---

# R9S Billing Records

当输入是 R9S 的 billing 响应 JSON，或需要解释 这类数据结构时，使用这个 skill。

目标是帮助 agent 正确理解：

- 顶层响应结构
- `data.list` 中每条计费记录的含义
- `ext` 中的扩展计费信息
- 哪些字段适合拿去和 usage 做对账

当需要精确查看 `ext` 的 schema、示例和扩展规则时，读取 `references/ext-schema.md`。

## 顶层结构

R9S billing 响应的顶层结构通常是：

- `meta`
- `data`

其中：

- `meta.code`
  表示接口调用状态，`0` 通常表示成功
- `meta.message`
  错误或补充信息，成功时可能为空字符串
- `meta.request_id`
  本次 billing 查询请求本身的 request id，不是 `data.list` 中业务调用的 request id

- `data.list`
  计费记录数组，每个元素代表一条单独的 billing record
- `data.total`
  返回的记录数量

## 单条计费记录结构

`data.list` 中每个对象表示一条计费记录。常见字段包括：

- `id`
  这条 billing record 的唯一标识
- `request_time`
  业务请求发生时间，一般是 Unix 时间戳
- `user_id`
  用户标识
- `custom_user_id`
  自定义用户标识，可能为空
- `token_id`
  价格或计费配置对应的 token / price card 标识
- `model`
  模型名称
- `model_type`
  模型类型，例如 `text` 或 `others`
- `input_token`
  主输入 token 数
- `output_token`
  主输出 token 数
- `input_price`
  输入 token 单价
- `output_price`
  输出 token 单价
- `cached_token`
  cached token 数
- `cached_price`
  cached token 单价
- `total_amount`
  计费总额
- `discount_amount`
  折扣金额
- `amount`
  实收金额
- `channel_id`
  渠道标识
- `ext`
  扩展计费信息，承载多模态、工具调用等额外费用明细

## 基础计费字段如何理解

基础对账时，优先关注这些字段：

- `model`
- `request_time`
- `input_token`
- `output_token`
- `cached_token`
- `input_price`
- `output_price`
- `cached_price`
- `total_amount`
- `amount`

这些字段通常可以用于和 usage 的基础 token 信息做对比。

## ext 字段的作用

`ext` 是最重要的扩展区域，用来表示基础 token 之外的附加计费信息。

不要把 `ext` 当作可忽略字段。对于多模态模型或带工具调用的模型，`ext` 可能正是解释费用差异的关键。

`ext` 常见可能为空对象：

```json
{}
```

这通常表示当前记录没有额外的多模态或工具明细，或者相关费用已经完全体现在主字段中。

## ext.input_v2：多模态输入计费

当模型请求包含多模态输入时，`ext` 中可能出现：

- `ext.input_v2.audio`
- `ext.input_v2.video`
- `ext.input_v2.image`

每个模态对象通常包含：

- `unit`
  计费单位，例如 `mtoken`
- `price`
  该模态的单价
- `usage`
  该模态的使用量
- `amount`
  该模态对应的金额

这类字段常用于解释：

- 为什么 `input_token` 很小，但总费用不低
- 为什么 Gemini / 多模态模型的账单和纯文本模型不同
- 为什么存在 image、audio、video 等额外成本

## ext.tools：工具调用计费

当请求使用了工具时，`ext` 中可能出现：

- `ext.tools.web_search`

工具对象通常也包含：

- `unit`
  工具计费单位，例如 `each`
- `price`
  每次工具调用价格
- `usage`
  工具调用次数
- `amount`
  工具调用总费用

例如 `web_search`：

- `usage: 3`
  表示发生了 3 次 web search
- `amount: 0.003`
  表示这些 web search 共产生了对应费用

这类字段非常适合和 usage 侧的工具信息对账，例如：

- Anthropic 的 `server_tool_use.web_search_requests`
- 其他 provider 中的工具调用事件或 tool-use 统计

## 对账时的推荐读取顺序

当 agent 需要把 R9S billing 与 usage 匹配时，建议按下面的顺序读取单条 billing record：

1. 先读基础身份字段

- `id`
- `request_time`
- `model`
- `channel_id`

2. 再读主 token 字段

- `input_token`
- `output_token`
- `cached_token`

3. 再读金额字段

- `total_amount`
- `discount_amount`
- `amount`

4. 最后读 `ext`

重点检查：

- 是否存在 `input_v2`
- 是否存在 `tools`
- 是否存在 image / audio / video / web_search 等扩展计费项

## 对账解释原则

如果 usage 与 billing 的基础 token 看起来接近，但总金额仍有差异，优先检查 `ext`。

常见解释路径：

- 基础 token 接近，但 `ext.tools.web_search` 产生了额外费用
- 主输入 token 很少，但 `ext.input_v2.image` / `audio` / `video` 带来了额外多模态成本
- 存在 `cached_token` 和 `cached_price`，说明 cache 费用需要单独解释

不要只比较：

- `input_token`
- `output_token`
- `total_amount`

而忽略 `ext`，否则很容易把“正常的扩展计费”误判为 mismatch。

## 行为约束

- 将 `data.list` 视为 billing records 数组，不要把顶层 `meta.request_id` 当成业务记录 id
- 将 `ext` 视为扩展计费明细，不要忽略
- `ext` 为空对象时，不代表记录异常
- 如果 `ext` 中存在多模态或工具字段，应将其纳入对账说明
- 在解释 mismatch 时，优先说明是否检查过 `ext`

## 当前已知示例

基于 `src/audit/mockBillingR9S.json`，当前可见的 `ext` 示例包括：

- `ext.tools.web_search`
- `ext.input_v2.audio`
- `ext.input_v2.video`
- `ext.input_v2.image`
- 空对象 `ext: {}`

后续如果 R9S 增加新的扩展计费项，应优先把它们看作 `ext` 的同类扩展字段，再决定是否补充新的映射规则。
