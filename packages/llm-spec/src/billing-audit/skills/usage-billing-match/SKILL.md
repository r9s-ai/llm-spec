---
name: usage-billing-match
description: 当用户提供一批 usage 记录和一批 billing 记录，并希望 agent 自动识别可能对应关系、完成匹配、解释差异、输出审计结论时使用。
---

# Usage Billing Match

当输入是一批 usage 记录和一批 billing 记录时，使用这个 skill。目标不是重放请求，而是让 agent 学会根据字段特征、时间窗口、模型信息和 token 数据，自动寻找最可能的对应关系。

## 任务目标

给定两组数据：

- 一组 usage 记录
- 一组 billing 记录

agent 需要完成：

1. 识别两组数据中可用于关联的字段
2. 为每条 usage 找到最可能对应的 billing
3. 标记无法唯一匹配的记录
4. 输出匹配结果与不匹配原因

## 输入假设

usage 和 billing 的来源可以变化，但建议先抽取出这些信息：

- provider
- model
- 请求时间或时间窗口
- 输入 token
- 输出 token
- 总 token
- cached token
- 金额
- request id / trace id / record id（如果存在）

如果原始字段名不同，先做语义映射，再比较。

## 计费对比时必须关注的信息

计费对比的重点是先对齐输入 token 和输出 token，再用其他字段解释差异来源。

不要只看总金额，也不要只看字段名是否相同。凡是可能影响“输入口径”或“输出口径”解释的信息，都应尽量保留。

优先关注这些维度：

- 输入 token
- 输出 token
- 总 token
- cached token
- web search 次数或服务端工具调用次数
- 多模态拆分信息
- 金额信息
- service tier / traffic type / inference geo 等附加上下文

这些字段不一定都单独参与“强匹配”，但它们常常用于解释为什么 usage 与 billing 的输入/输出金额能够对上，或者为什么看起来接近却仍然不能直接判定一致。

其中下列字段默认视为核心计费字段：

- 输入 token
- 输出 token
- cached token
- 多模态拆分中的 image / audio / video / document 等实际参与计费的 usage
- web search 等工具调用次数或其他 billing 已单独列出的工具计费维度

只要这些核心计费字段中有任意一项在 usage 与 billing 之间无法对齐，就不能判为 `matched`。

## 匹配优先级

按照下面的顺序寻找关联关系。越靠前的条件权重越高。

1. 明确关联键

优先使用这些字段直接匹配：

- request id
- trace id
- supplier request id
- 平台侧 request id

如果 usage 和 billing 之间存在明确唯一键，优先直接匹配，不要退回模糊匹配。

2. 模型和 provider

如果没有明确关联键，先按这些字段缩小候选范围：

- provider
- model

不同 provider 的记录不要互相匹配。

3. 时间接近度

在 provider 和 model 一致的前提下，优先选择时间最接近的 billing 记录。

建议原则：

- 优先匹配同一时间窗口内的记录
- 如果只有单点时间，优先匹配时间差最小的记录
- 如果时间差明显过大，应降低匹配置信度

4. token 特征

进一步比较这些字段：

- 输入 token
- 输出 token
- 总 token
- cached token

如果 token 结构高度接近，该 billing 记录优先级更高。

5. 金额特征

如果 billing 提供金额信息，可以把金额作为辅助信号：

- 总金额是否合理
- 输入 / 输出 / cached 金额是否与 token 结构一致

金额只能作为辅助判断，不要在缺少 token 对应关系时只靠金额强行匹配。

注意：

- “找到了最像的一条 billing” 不等于 “审计通过”
- 即使候选唯一、模型一致、时间接近，只要核心计费字段存在任何差异，状态也必须是 `mismatched`
- 不允许因为“只差 1 个 token”“差异很小”“整体看起来接近”就继续标成 `matched`

## 字段归一化原则

不同 provider 的 usage 字段名不同，匹配前先归一化语义。

归一化时，要先回答两个问题：

1. 哪些字段代表主输入 token / 主输出 token
2. 哪些字段只是对输入或输出的拆分说明，或者是辅助解释字段

默认口径：

- “输入 token”
  指 billing 主体中应与请求输入成本对应的 token 数
- “输出 token”
  指 billing 主体中应与模型响应成本对应的 token 数
- `cached token`
  单独保留，用于解释 cache 命中或 cache 相关计费
- 多模态明细
  视为输入 token 的拆分说明；如果 billing 把多模态单独放在 `ext`，应与这些明细联合解释
- 工具调用次数
  视为扩展计费解释字段；如果 billing 对工具单独收费，就必须纳入比对
- `reasoning_tokens` / `thoughtsTokenCount`
  默认先视为输出侧的拆分说明，不单独作为独立主字段；只有当 billing 明确把 reasoning / thinking 单独列账时，才把它作为单独比对项
- `toolUsePromptTokenCount`
  默认视为输入侧的拆分说明，表示工具结果回灌给模型所形成的输入；如果 billing 主输入 token 已覆盖这部分，则不要求单独列一栏；只有当 billing 单独拆分该项时，才做逐项比对

常见映射：

- OpenAI chat
  - `prompt_tokens` -> 输入 token
  - `completion_tokens` -> 输出 token
  - `total_tokens` -> 总 token
  - `prompt_tokens_details.cached_tokens` -> cached token
  - `prompt_tokens_details.audio_tokens` -> 输入侧 audio token 拆分
  - `completion_tokens_details.audio_tokens` -> 输出侧 audio token 拆分
  - `completion_tokens_details.reasoning_tokens` -> 输出侧 reasoning token 拆分，一般用于解释输出成本，不默认要求 billing 单独列出

- OpenAI responses
  - `input_tokens` -> 输入 token
  - `output_tokens` -> 输出 token
  - `total_tokens` -> 总 token
  - `input_tokens_details.cached_tokens` -> cached token
  - `output_tokens_details.reasoning_tokens` -> 输出侧 reasoning token 拆分，一般用于解释输出成本，不默认要求 billing 单独列出

- Anthropic
  - `input_tokens` -> 输入 token
  - `output_tokens` -> 输出 token
  - `cache_creation_input_tokens` / `cache_read_input_tokens` -> cache 相关输入 token，单独保留用于解释 cache 口径
  - `server_tool_use.web_search_requests` -> 服务端 web search 请求次数
  - `service_tier` -> 推理服务层级
  - `inference_geo` -> 推理地理区域

- Gemini
  - `promptTokenCount` -> 输入 token
  - `candidatesTokenCount` -> 输出 token
  - `totalTokenCount` -> 总 token
  - `cachedContentTokenCount` -> cached token
  - `promptTokensDetails` -> 输入侧按模态拆分的 token 明细
  - `candidatesTokensDetails` -> 输出侧按模态拆分的 token 明细
  - `cacheTokensDetails` -> cache 按模态拆分的 token 明细
  - `toolUsePromptTokenCount` -> 输入侧拆分字段，表示工具结果回灌给模型形成的输入 token
  - `toolUsePromptTokensDetails` -> 上述输入回灌的模态拆分明细
  - `thoughtsTokenCount` -> 输出侧 thinking / thoughts 拆分字段，一般用于解释输出成本，不默认要求 billing 单独列出
  - `trafficType` -> 流量类型

不要因为字段名不同就认为无法比较。

### OpenAI 特别说明

OpenAI 的 usage 通常可以直接反映：

- 基础输入 / 输出 / 总 token
- cached token
- 输入或输出中的细分 token，例如 reasoning token、audio token
- 某些图像场景下的 image token / text token 拆分

但是 OpenAI 的 web search 信息通常不是直接体现在 usage 计数字段里，而更可能体现在 response 事件或 tool call 结构中。因此：

- 不要默认 OpenAI usage 一定能直接给出 web search 次数
- 如果 billing 中出现了与 web search 相关的计费项，应结合 response 中的工具调用信息，而不是只依赖 usage

### Anthropic 特别说明

Anthropic 的 usage 对计费对比很有价值，因为它不仅提供 token，还可能直接反映服务端工具使用情况。

重点关注：

- `input_tokens`
- `output_tokens`
- `cache_creation_input_tokens`
- `cache_read_input_tokens`
- `server_tool_use.web_search_requests`
- `service_tier`
- `inference_geo`

其中：

- `server_tool_use.web_search_requests` 可以直接用于解释 web search 相关计费
- `cache_creation_input_tokens` / `cache_read_input_tokens` 可以用于解释 cache 计费或 cache 命中差异
- `service_tier` 在某些场景下可能影响费用解释

### Gemini 特别说明

Gemini 的 usage 建议保留两层信息：

- 总量字段
  - `promptTokenCount`
  - `candidatesTokenCount`
  - `totalTokenCount`
  - `cachedContentTokenCount`
  - `toolUsePromptTokenCount`
  - `thoughtsTokenCount`

- 模态明细字段
  - `promptTokensDetails`
  - `candidatesTokensDetails`
  - `cacheTokensDetails`
  - `toolUsePromptTokensDetails`

模态明细里常见的 `modality` 可能包括：

- `TEXT`
- `IMAGE`
- `VIDEO`
- `AUDIO`
- `DOCUMENT`
- 其他 provider 扩展值

对于 Gemini，匹配时建议：

1. 先比较总量字段
2. 再比较各模态拆分是否合理
3. `toolUsePromptTokenCount` 视为输入侧补充说明，`thoughtsTokenCount` 视为输出侧补充说明；除非 billing 单独列出它们，否则先不要把它们当成独立主字段
4. 如果总量接近但某个模态明显不一致，应降低匹配置信度
5. 如果 billing 侧也有 image / audio / video 等拆分计费，优先用模态明细解释差异

### 计费解释原则

在 usage 与 billing 做对比时：

- 输入 / 输出 / 总 token 用于基础匹配
- cached token 用于解释 cache 费用或折扣差异
- reasoning / thoughts token 默认作为输出侧拆分说明
- toolUsePromptTokenCount 默认作为输入侧拆分说明
- web search 次数用于解释搜索工具相关计费
- 多模态拆分用于解释 image / audio / video / document 等差异化计费

如果 billing 中有明细计费项，而 usage 中也有对应维度，应优先按维度解释，不要只比较总金额。

## 匹配策略

对于每条 usage，执行以下流程：

1. 先找具有相同明确关联键的 billing 记录
2. 如果没有明确关联键，就筛选 provider 相同、model 相同的 billing 候选
3. 在候选中按时间接近度排序
4. 再按 token 相似度排序
5. 如果仍有多个高相似候选，不要猜，标记为 `unresolved`

如果多条 usage 指向同一条 billing，也要检查是否真的合理。默认情况下，一条 billing 只应对应一条 usage，除非输入数据明确说明可以聚合。

## 输出分类

每条 usage 最终应落入以下状态之一：

- `matched`
  存在一个唯一高置信度 billing 候选，且核心计费字段严格一致

- `mismatched`
  存在一个最可能的 billing 候选，但任一核心计费字段不一致

- `unresolved`
  没有足够信息选出唯一候选，或没有合理候选

- `missing_billing`
  usage 看起来有效，但找不到任何合理的 billing 候选

## 输出要求

最终结果至少包含：

- usage 记录标识
- 候选 billing 记录标识
- 匹配状态
- 不匹配原因或无法判定原因

如果是批量结果，还应包含：

- 总 usage 数量
- 成功匹配数量
- mismatch 数量
- unresolved 数量
- missing_billing 数量

## 表格输出格式

如果是批量审计，最终输出建议固定为“两张表 + 一段结论”。

先输出汇总表，再输出逐条明细表，最后再补充总体观察和需要人工复核的点。

### 1. 汇总表

建议输出一个总览表，快速说明这批 usage 的审计结果：

| 总usage数 | matched | mismatched | unresolved | missing_billing |
| --- | --- | --- | --- | --- |
| 30 | 24 | 3 | 2 | 1 |

### 2. 逐条审计明细表

每条 usage 输出一行，建议至少包含这些列：

| usage序号 | provider | model | 候选billing id | 状态 | 原因 |
| --- | --- | --- | --- | --- | --- |
| 1 | gemini | gemini-2.5-pro | 3374672231635158179 | matched |  |

这张逐条审计明细表必须满足：

- 行数必须和输入 usage 记录数完全一致
- 每一条 usage 都必须在表格中出现，不能省略，不能只展示异常项
- 即使某条记录无法匹配，也必须输出一行，并标记为 `unresolved` 或 `missing_billing`
- 不允许把多条 usage 合并成一行展示，除非输入数据明确说明这些 usage 本身就是聚合记录

各列填写建议：

- `usage序号`
  建议使用输入 usage 数组中的顺序编号，从 1 开始。若原始数据中已有稳定标识，也可以写成 `3 (usage_id=xxx)` 这种形式。

- `provider`
  统一写归一化后的 provider，例如 `openai`、`anthropic`、`gemini`。

- `model`
  写归一化后的模型名。不要混用原始别名和归一化名。

- `候选billing id`
  填最可能对应的 billing record id。
  如果没有合理候选，填 `-`。
  如果存在多个高相似候选但无法唯一确定，可以填 `id1 / id2 / id3`，并将状态标为 `unresolved`。

- `状态`
  只使用这几个值：
  - `matched`
  - `mismatched`
  - `unresolved`
  - `missing_billing`

- `原因`
  这个字段默认只给异常项使用。
  如果状态是 `matched`，原因列留空即可，不需要填写“匹配”“一致”“对得上”之类内容。
  如果状态是 `mismatched`、`unresolved` 或 `missing_billing`，再用一句短话总结为什么得出这个状态。优先提最关键的 1 到 3 个证据，不要写成长段。
  由于表格列数精简，原本的输入对比、输出对比、cache 对比、工具/多模态对比、金额判断，都应在需要时压缩写进这一列。
  建议优先包含：
  - 是否存在输入 token / 输出 token / cache 的差异
  - 是否存在工具次数或多模态 usage 的差异
  - 如果 billing 的 `ext` 解释不了差异，也应在这里点明
  - 如果判断依据不足，也应在这里说明为什么是 `unresolved`

  推荐写法示例：
  - `输入 token 差 1，虽候选唯一但按严格审计记为 mismatched`
  - `web_search 次数对不上，billing ext 缺少对应工具计费`
  - `存在两个同模型候选，缺少时间与 request id，无法唯一确定`
  - `未找到任何同 provider 同 model 的合理候选账单`

### 3. 状态值的判定口径

输出表格时，状态要和判定逻辑保持一致：

- `matched`
  已找到唯一高置信候选，且所有核心计费字段严格一致，扩展计费也能逐项解释

- `mismatched`
  已找到最可能候选，但任一核心计费字段不一致，例如输入 token 差 1、输出 token 差 1、cache 不一致、工具次数不一致，或多模态费用对应的 usage 对不上

- `unresolved`
  存在多个相似候选，或关键信息不足，暂时不能唯一确定

- `missing_billing`
  usage 看起来有效，但在 billing 中没有找到合理候选

### 4. 表格填写约束

- 不要在表格里写“可能差不多”“应该是这条”这类含糊说法。无法确定就标 `unresolved`
- 如果 billing 的 `input_token` / `output_token` 只反映文本，而多模态或工具费用在 `ext`，必须在“原因”列中说明
- 如果 usage 侧没有时间、没有 request id，就不要假装有强证据；此时更要依赖 model、token结构和扩展计费特征
- 如果一条记录存在多个冲突点，“原因”列里只写最关键的冲突，详细解释可放到表格后面的补充说明
- 如果状态是 `matched`，“原因”列应留空，不要写冗余的成功说明
- 若最终输出给人看，优先保证每一行都能单独读懂，不要把关键理由藏在表格外
- 输出前要自检一次：逐条审计明细表的行数是否与输入 usage 条数一致；如果不一致，说明输出不完整，需要继续补齐
- 对审计任务采用严格一致原则：核心计费字段只要差 1，也算不一致，必须标为 `mismatched`
- 不允许把“差异很小”当成“可以忽略”；审计的目标是发现差异，不是近似匹配

### 5. 表格后的结论段

表格之后建议补一小段总结，至少说明：

- 这一批数据整体是“多数可匹配”还是“存在较多异常”
- 主要异常集中在哪类问题
  例如：`web_search 计费缺失`、`Gemini 多模态明细未对齐`、`cache 字段口径不一致`
- 哪些记录建议人工复核

如果存在明显模式，也应直接指出，例如：

- 某一类 provider 的 tool use 记录系统性缺失
- 某一类模型的 image/audio/video 费用都只出现在 billing ext 中
- 某些 mismatch 实际上是字段口径差异，不一定是漏计或错计

## 行为约束

- 优先做语义归一化，再做匹配
- 优先使用强关联键，再使用时间和 token 特征
- 没有足够证据时，返回 `unresolved`
- 不要为了提高匹配率而强行一一对应
- 解释结论时，指出使用了哪些字段进行判断
- 如果发现额外计费信息，例如 web search、cache、reasoning、多模态 token，不要忽略，应在结论中说明这些信息是否支持当前匹配关系
- 如果发现 `reasoning_tokens`、`thoughtsTokenCount`、`toolUsePromptTokenCount` 这类拆分字段，默认先把它们用于解释输入/输出口径，不要在 billing 未单列时自动判定为独立漏计
- 如果无法理解 billing 结构中某些核心字段的业务含义，例如不知道某个 token 字段、金额字段、扩展字段、状态字段到底代表什么，就不要继续猜测匹配逻辑，应停止任务并明确要求用户先解释 billing 结构的意义，再继续审计

## 可替换部分

这个 skill 允许替换三类内容，而不改变整体目标：

- usage 的数据来源
- billing 的数据来源
- 归一化字段映射

无论输入来源如何变化，agent 的核心职责都不变：从两批记录中找出最可能的对应关系，并清楚说明依据。
