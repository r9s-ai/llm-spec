# LLM-Spec 架构文档

## 项目概述

LLM-Spec 是一个规范驱动的 LLM API 厂商兼容性测试工具，用于验证各厂商API的参数支持情况和响应格式合规性，并生成细粒度的测试报告。

## 项目结构

```
llm-spec/
├── llm_spec/                      # 核心代码
│   ├── ...                        # (省略 client, providers, validation, reporting)
├── tests/                         # 测试系统
│   ├── test_from_config.py        # 统一测试入口（配置驱动）
│   ├── conftest.py                # Pytest 全局 fixtures
│   ├── runners/                   # 测试执行核心逻辑
│   │   ├── base.py                # ConfigDrivenTestRunner (核心逻辑)
│   │   └── schema_registry.py     # Schema 注册中心
│   ├── testcases/                 # 测试用例配置 (JSON5)
│   │   ├── openai/                # OpenAI 系列配置
│   │   ├── gemini/                # Gemini 系列配置
│   │   ├── anthropic/             # Anthropic 系列配置
│   │   └── xai/                   # xAI 系列配置
│   ├── legacy/                    # 旧版纯 Python 测试 (保留参考)
│   │   ├── openai/
│   │   └── gemini/
├── test_assets/                   # 测试资源文件 (音频, 图片)
├── reports/                       # 生成的报告目录
```
├── temp/                          # 临时文件（按时间戳分目录）
├── reports/                       # 生成的报告目录
│   └── {provider}_{endpoint}_{timestamp}/  # 每个测试一个子目录
│       ├── report.json            # JSON 格式报告
│       ├── parameters.md          # Markdown 参数表格
│       └── report.html            # HTML 格式报告
├── logs/                          # 应用日志
├── llm-spec.toml                  # 配置文件
└── pyproject.toml                 # 项目元数据
```

## 架构分层

### 第一层：配置与日志 (config + client/logger)
**职责**：配置管理、日志记录
- 解析 `llm-spec.toml` 配置文件
- 提供结构化日志（带request_id追踪）
- 支持控制台和文件日志输出

### 第二层：HTTP客户端 (client)
**职责**：HTTP通信
- 抽象接口：`BaseHTTPClient` 定义标准方法
- 具体实现：`HTTPClient` 基于 httpx
- 支持：同步/异步、流式/非流式
- 自动错误处理和日志记录

### 第三层：Provider适配器 (providers)
**职责**：各厂商API适配
- 使用**组合模式**（持有HTTPClient，而非继承）
- 准备厂商特定的请求头（如认证）
- 拼接完整URL（base_url + endpoint）
- 委托HTTPClient执行请求

### 第四层：验证系统 (validation)
**职责**：响应格式验证
- **递归字段提取**：自动提取所有嵌套字段（如 `choices.message.role`、`usage.prompt_tokens`）
- **字段级验证**：精确定位缺失或错误的字段
- **类型验证**：确保字段值符合 schema 定义
- Pydantic模型定义期望的响应结构

### 第五层：报告系统 (reporting)
**职责**：测试结果汇总、参数表格生成
- 收集测试参数、状态码、错误信息
- **递归嵌套参数提取**：自动提取嵌套字典和数组中的参数路径（如 `generationConfig.temperature`、`messages[0].role`）
- 跟踪不支持的参数和缺失的响应字段
- 生成 JSON、Markdown、HTML 格式报告

**ReportCollector 核心功能**：
```python
@staticmethod
def _extract_param_paths(params: dict[str, Any], prefix: str = "", max_depth: int = 10) -> set[str]:
    """递归提取参数路径（支持嵌套结构）

    示例：
    - 扁平结构 (OpenAI): {"temperature": 0.7} → ["temperature"]
    - 嵌套字典 (Gemini): {"generationConfig": {"temperature": 0.7}}
      → ["generationConfig", "generationConfig.temperature"]
    - 数组字典 (Anthropic): {"messages": [{"role": "user"}]}
      → ["messages", "messages[0].role"]
    """
```

这确保了报告中的 `parameters.tested` 字段包含所有被明确记录的参数路径。

**ParameterTableFormatter 核心功能**：
```python
class ParameterTableFormatter:
    """参数支持情况格式化器

    直接从 JSON 报告的 tested_params 生成表格：
    - 只显示被明确记录的参数（通过 test_param 或 is_baseline）
    - 自动检测支持/不支持状态
    - 支持 Markdown 和 HTML 两种输出格式
    """

    def __init__(self, report_data: dict):
        # 从报告中提取：
        # - tested_params: 已测试的参数列表
        # - supported_params: 支持的参数列表
        # - unsupported_params: 不支持的参数及原因
        # - test_summary: 测试统计（总数、通过、失败）

    def generate_markdown(self) -> str:
        """生成简洁的 Markdown 表格"""

    def generate_html(self) -> str:
        """生成美观的 HTML 报告"""
```

**报告目录结构**：
```
reports/
└── openai_v1_chat_completions_20260129_191805/  # provider_endpoint_timestamp
    ├── report.json              # JSON 格式（原始数据）
    ├── parameters.md            # Markdown 格式（参数表格）
    └── report.html              # HTML 格式（美观展示）
```

### 第六层：测试引擎层 (tests)
**职责**：执行具体的 API 测试
- **引擎入口**: `tests/test_from_config.py` 利用 Pytest 参数化机制驱动测试。
- **配置驱动**: 通过读取 `tests/testcases/` 下的 JSON5 文件动态生成用例，无需编写手写 Python 测试。
- **Runner**: `ConfigDrivenTestRunner` 负责参数合并、自动包装映射、HTTP 发起及响应 Schema 校验。

## 设计原则

### 1. 关注点分离
- **HTTP 客户端** 不知道 Provider 的存在。
- **Provider 适配器** 不知道验证逻辑。
- **验证器** 不知道报告格式。
- 每层职责单一，接口清晰。

### 2. 声明式优先 (Configuration First)
- 测试用例使用 JSON5 编写，支持注释，逻辑与数据完全分离。
- 新增测试用例仅需增加配置文件，无需改动核心代码。

### 3. 组合优于继承
- Provider 持有 HTTPClient 实例而非继承，保证了各组件的独立演化能力。

---

## 开发与扩展指南

本项目已采用**配置驱动测试方案**。具体的添加步骤、配置规范及实战案例，请参阅专门的指南文档：

👉 **[配置驱动测试指南 (CONFIG_DRIVEN_TESTING.md)](CONFIG_DRIVEN_TESTING.md)**

### 旧版测试 (Legacy)
原有的部分手写 Python 测试已移至 `tests/legacy/` 目录，仅供逻辑参考，不再作为主要的测试维护手段。

---

## 报告格式说明

生成的报告包含三种格式，详细记录了参数覆盖率和厂商兼容性：

1. **JSON 报告 (report.json)**：包含所有原始数据。
2. **Markdown 概览 (parameters.md)**：直观的参数支持状态表格。
3. **HTML 报告 (report.html)**：美观的交互式展现。

---

## License

MIT
- [ ] 实现报告自动清理（保留最近N次测试）

### 长期
- [ ] 实现自动化CI/CD测试流程
- [ ] 支持性能基准测试（响应时间统计）
- [ ] 生成对比报告（新旧版本API差异）
- [ ] 实现Web UI查看报告

---

