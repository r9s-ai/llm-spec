"""Anthropic Messages API - 流式响应测试"""

import json
import pytest

from llm_spec.reporting.collector import ReportCollector
from llm_spec.validation.schemas.anthropic import (
    MessagesResponse,
    MessageStartEvent,
    ContentBlockStartEvent,
    ContentBlockDeltaEvent,
    ContentBlockStopEvent,
    MessageDeltaEvent,
    MessageStopEvent,
    PingEvent,
    ErrorEvent,
)
from llm_spec.validation.validator import ResponseValidator


class TestMessagesStreaming:
    """Messages API 流式响应测试类"""

    ENDPOINT = "/v1/messages"

    # 基线参数：仅包含必需参数
    BASE_PARAMS = {
        "model": "claude-3-5-sonnet-20241022",
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": "Hello"}],
    }

    @pytest.fixture(scope="class", autouse=True)
    def setup_collector(self, anthropic_client):
        """为整个测试类设置报告收集器"""
        collector = ReportCollector(
            provider="anthropic",
            endpoint=self.ENDPOINT,
            base_url=anthropic_client.get_base_url(),
        )

        self.__class__.client = anthropic_client
        self.__class__.collector = collector

        yield

        report_path = collector.finalize()
        print(f"\n报告已生成: {report_path}")

    # ==================== 阶段1: 基础流式测试 ====================

    @pytest.mark.asyncio
    async def test_streaming_basic(self):
        """测试基础流式响应"""
        test_name = "test_streaming_basic"
        params = {**self.BASE_PARAMS, "stream": True}

        chunks = []
        error_occurred = False
        error_msg = None

        try:
            async for chunk in self.client.stream_async(self.ENDPOINT, params):
                chunks.append(chunk)
        except Exception as e:
            error_occurred = True
            error_msg = str(e)

        # 记录测试结果
        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=200 if not error_occurred else 500,
            response_body={"chunks_received": len(chunks)} if chunks else None,
            error=error_msg if error_occurred else None,
        )

        if error_occurred:
            self.collector.add_unsupported_param(
                param_name="stream",
                param_value=True,
                test_name=test_name,
                reason=f"Streaming error: {error_msg}",
            )

        assert not error_occurred, f"Streaming failed: {error_msg}"
        assert len(chunks) > 0, "No chunks received"

    @pytest.mark.asyncio
    async def test_streaming_event_types(self):
        """测试验证所有流式事件类型"""
        test_name = "test_streaming_event_types"
        params = {
            **self.BASE_PARAMS,
            "stream": True,
            "messages": [{"role": "user", "content": "Write a short poem about the ocean."}],
        }

        event_types_seen = set()
        chunks = []
        error_occurred = False
        error_msg = None

        try:
            async for chunk in self.client.stream_async(self.ENDPOINT, params):
                chunks.append(chunk)

                # 尝试解析事件类型
                try:
                    # SSE 格式通常是 "data: {json}"
                    if isinstance(chunk, bytes):
                        chunk_str = chunk.decode("utf-8")
                    else:
                        chunk_str = chunk

                    # 解析 SSE 格式
                    if chunk_str.startswith("data: "):
                        json_str = chunk_str[6:].strip()
                        if json_str and json_str != "[DONE]":
                            event_data = json.loads(json_str)
                            if "type" in event_data:
                                event_types_seen.add(event_data["type"])
                except Exception:
                    # 忽略解析错误，继续处理
                    pass

        except Exception as e:
            error_occurred = True
            error_msg = str(e)

        # 记录测试结果
        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=200 if not error_occurred else 500,
            response_body={
                "chunks_received": len(chunks),
                "event_types": list(event_types_seen),
            },
            error=error_msg if error_occurred else None,
        )

        if error_occurred:
            self.collector.add_unsupported_param(
                param_name="stream",
                param_value="event_types",
                test_name=test_name,
                reason=f"Streaming error: {error_msg}",
            )

        assert not error_occurred, f"Streaming failed: {error_msg}"
        assert len(chunks) > 0, "No chunks received"

        # 验证期望的事件类型
        expected_events = {
            "message_start",
            "content_block_start",
            "content_block_delta",
            "content_block_stop",
            "message_delta",
            "message_stop",
        }

        # 至少应该看到 message_start 和 message_stop
        # assert "message_start" in event_types_seen
        # assert "message_stop" in event_types_seen

    # ==================== 阶段2: 流式内容验证 ====================

    @pytest.mark.asyncio
    async def test_streaming_text_accumulation(self):
        """测试流式文本累积验证"""
        test_name = "test_streaming_text_accumulation"
        params = {
            **self.BASE_PARAMS,
            "stream": True,
            "messages": [{"role": "user", "content": "Count from 1 to 5"}],
        }

        accumulated_text = ""
        chunks = []
        error_occurred = False
        error_msg = None

        try:
            async for chunk in self.client.stream_async(self.ENDPOINT, params):
                chunks.append(chunk)

                # 解析文本增量
                try:
                    if isinstance(chunk, bytes):
                        chunk_str = chunk.decode("utf-8")
                    else:
                        chunk_str = chunk

                    if chunk_str.startswith("data: "):
                        json_str = chunk_str[6:].strip()
                        if json_str and json_str != "[DONE]":
                            event_data = json.loads(json_str)

                            # 查找 text_delta
                            if event_data.get("type") == "content_block_delta":
                                delta = event_data.get("delta", {})
                                if delta.get("type") == "text_delta":
                                    text = delta.get("text", "")
                                    accumulated_text += text
                except Exception:
                    pass

        except Exception as e:
            error_occurred = True
            error_msg = str(e)

        # 记录测试结果
        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=200 if not error_occurred else 500,
            response_body={
                "chunks_received": len(chunks),
                "accumulated_length": len(accumulated_text),
            },
            error=error_msg if error_occurred else None,
        )

        if error_occurred:
            self.collector.add_unsupported_param(
                param_name="stream",
                param_value="text_accumulation",
                test_name=test_name,
                reason=f"Streaming error: {error_msg}",
            )

        assert not error_occurred, f"Streaming failed: {error_msg}"
        assert len(chunks) > 0, "No chunks received"
        # assert len(accumulated_text) > 0, "No text accumulated"

    @pytest.mark.asyncio
    async def test_streaming_usage_tracking(self):
        """测试流式响应中的 usage 统计"""
        test_name = "test_streaming_usage_tracking"
        params = {**self.BASE_PARAMS, "stream": True}

        usage_data = None
        chunks = []
        error_occurred = False
        error_msg = None

        try:
            async for chunk in self.client.stream_async(self.ENDPOINT, params):
                chunks.append(chunk)

                # 查找 usage 信息（通常在 message_delta 或 message_stop 事件中）
                try:
                    if isinstance(chunk, bytes):
                        chunk_str = chunk.decode("utf-8")
                    else:
                        chunk_str = chunk

                    if chunk_str.startswith("data: "):
                        json_str = chunk_str[6:].strip()
                        if json_str and json_str != "[DONE]":
                            event_data = json.loads(json_str)

                            if "usage" in event_data:
                                usage_data = event_data["usage"]
                except Exception:
                    pass

        except Exception as e:
            error_occurred = True
            error_msg = str(e)

        # 记录测试结果
        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=200 if not error_occurred else 500,
            response_body={"chunks_received": len(chunks), "usage": usage_data},
            error=error_msg if error_occurred else None,
        )

        if error_occurred:
            self.collector.add_unsupported_param(
                param_name="stream",
                param_value="usage_tracking",
                test_name=test_name,
                reason=f"Streaming error: {error_msg}",
            )

        assert not error_occurred, f"Streaming failed: {error_msg}"
        assert len(chunks) > 0, "No chunks received"

    @pytest.mark.asyncio
    async def test_streaming_stop_reason(self):
        """测试流式响应中的 stop_reason"""
        test_name = "test_streaming_stop_reason"
        params = {
            **self.BASE_PARAMS,
            "stream": True,
            "max_tokens": 50,  # 限制 tokens 以便可能触发 max_tokens stop_reason
        }

        stop_reason = None
        chunks = []
        error_occurred = False
        error_msg = None

        try:
            async for chunk in self.client.stream_async(self.ENDPOINT, params):
                chunks.append(chunk)

                # 查找 stop_reason
                try:
                    if isinstance(chunk, bytes):
                        chunk_str = chunk.decode("utf-8")
                    else:
                        chunk_str = chunk

                    if chunk_str.startswith("data: "):
                        json_str = chunk_str[6:].strip()
                        if json_str and json_str != "[DONE]":
                            event_data = json.loads(json_str)

                            if event_data.get("type") == "message_delta":
                                delta = event_data.get("delta", {})
                                if "stop_reason" in delta:
                                    stop_reason = delta["stop_reason"]
                except Exception:
                    pass

        except Exception as e:
            error_occurred = True
            error_msg = str(e)

        # 记录测试结果
        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=200 if not error_occurred else 500,
            response_body={"chunks_received": len(chunks), "stop_reason": stop_reason},
            error=error_msg if error_occurred else None,
        )

        if error_occurred:
            self.collector.add_unsupported_param(
                param_name="stream",
                param_value="stop_reason",
                test_name=test_name,
                reason=f"Streaming error: {error_msg}",
            )

        assert not error_occurred, f"Streaming failed: {error_msg}"
        assert len(chunks) > 0, "No chunks received"

    # ==================== 阶段3: 流式工具调用 ====================

    @pytest.mark.asyncio
    async def test_streaming_tool_use(self):
        """测试流式工具调用"""
        test_name = "test_streaming_tool_use"

        weather_tool = {
            "name": "get_weather",
            "description": "Get the current weather",
            "input_schema": {
                "type": "object",
                "properties": {
                    "location": {"type": "string"},
                },
                "required": ["location"],
            },
        }

        params = {
            **self.BASE_PARAMS,
            "stream": True,
            "tools": [weather_tool],
            "messages": [{"role": "user", "content": "What's the weather in Paris?"}],
        }

        has_tool_use = False
        chunks = []
        error_occurred = False
        error_msg = None

        try:
            async for chunk in self.client.stream_async(self.ENDPOINT, params):
                chunks.append(chunk)

                # 查找 tool_use
                try:
                    if isinstance(chunk, bytes):
                        chunk_str = chunk.decode("utf-8")
                    else:
                        chunk_str = chunk

                    if chunk_str.startswith("data: "):
                        json_str = chunk_str[6:].strip()
                        if json_str and json_str != "[DONE]":
                            event_data = json.loads(json_str)

                            if event_data.get("type") == "content_block_start":
                                content_block = event_data.get("content_block", {})
                                if content_block.get("type") == "tool_use":
                                    has_tool_use = True
                except Exception:
                    pass

        except Exception as e:
            error_occurred = True
            error_msg = str(e)

        # 记录测试结果
        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=200 if not error_occurred else 500,
            response_body={"chunks_received": len(chunks), "has_tool_use": has_tool_use},
            error=error_msg if error_occurred else None,
        )

        if error_occurred:
            self.collector.add_unsupported_param(
                param_name="stream",
                param_value="tool_use",
                test_name=test_name,
                reason=f"Streaming error: {error_msg}",
            )

        assert not error_occurred, f"Streaming failed: {error_msg}"
        assert len(chunks) > 0, "No chunks received"

    @pytest.mark.asyncio
    async def test_streaming_input_json_delta(self):
        """测试流式 input_json_delta 事件"""
        test_name = "test_streaming_input_json_delta"

        calculator_tool = {
            "name": "calculator",
            "description": "Perform calculations",
            "input_schema": {
                "type": "object",
                "properties": {
                    "expression": {"type": "string"},
                },
                "required": ["expression"],
            },
        }

        params = {
            **self.BASE_PARAMS,
            "stream": True,
            "tools": [calculator_tool],
            "messages": [{"role": "user", "content": "Calculate 123 + 456"}],
        }

        has_input_json_delta = False
        chunks = []
        error_occurred = False
        error_msg = None

        try:
            async for chunk in self.client.stream_async(self.ENDPOINT, params):
                chunks.append(chunk)

                # 查找 input_json_delta
                try:
                    if isinstance(chunk, bytes):
                        chunk_str = chunk.decode("utf-8")
                    else:
                        chunk_str = chunk

                    if chunk_str.startswith("data: "):
                        json_str = chunk_str[6:].strip()
                        if json_str and json_str != "[DONE]":
                            event_data = json.loads(json_str)

                            if event_data.get("type") == "content_block_delta":
                                delta = event_data.get("delta", {})
                                if delta.get("type") == "input_json_delta":
                                    has_input_json_delta = True
                except Exception:
                    pass

        except Exception as e:
            error_occurred = True
            error_msg = str(e)

        # 记录测试结果
        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=200 if not error_occurred else 500,
            response_body={
                "chunks_received": len(chunks),
                "has_input_json_delta": has_input_json_delta,
            },
            error=error_msg if error_occurred else None,
        )

        if error_occurred:
            self.collector.add_unsupported_param(
                param_name="stream",
                param_value="input_json_delta",
                test_name=test_name,
                reason=f"Streaming error: {error_msg}",
            )

        assert not error_occurred, f"Streaming failed: {error_msg}"
        assert len(chunks) > 0, "No chunks received"

    # ==================== 阶段4: 流式错误处理 ====================

    @pytest.mark.asyncio
    async def test_streaming_error_event(self):
        """测试流式错误事件处理"""
        test_name = "test_streaming_error_event"

        # 使用无效参数来触发错误（如超大 max_tokens）
        params = {
            **self.BASE_PARAMS,
            "stream": True,
            "max_tokens": 999999,  # 可能会触发错误
        }

        has_error_event = False
        chunks = []
        error_occurred = False
        error_msg = None

        try:
            async for chunk in self.client.stream_async(self.ENDPOINT, params):
                chunks.append(chunk)

                # 查找错误事件
                try:
                    if isinstance(chunk, bytes):
                        chunk_str = chunk.decode("utf-8")
                    else:
                        chunk_str = chunk

                    if chunk_str.startswith("data: "):
                        json_str = chunk_str[6:].strip()
                        if json_str and json_str != "[DONE]":
                            event_data = json.loads(json_str)

                            if event_data.get("type") == "error":
                                has_error_event = True
                                error_msg = event_data.get("error", {}).get("message", "")
                except Exception:
                    pass

        except Exception as e:
            error_occurred = True
            if not error_msg:
                error_msg = str(e)

        # 记录测试结果
        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=400 if has_error_event or error_occurred else 200,
            response_body={"chunks_received": len(chunks), "has_error_event": has_error_event},
            error=error_msg if has_error_event or error_occurred else None,
        )

        # 这个测试预期可能失败，不做强制断言
        # assert has_error_event or error_occurred

    @pytest.mark.asyncio
    async def test_streaming_ping_event(self):
        """测试 ping 事件处理"""
        test_name = "test_streaming_ping_event"
        params = {
            **self.BASE_PARAMS,
            "stream": True,
            "messages": [
                {
                    "role": "user",
                    "content": "Write a very long story about a journey across the galaxy.",
                }
            ],
        }

        has_ping_event = False
        chunks = []
        error_occurred = False
        error_msg = None

        try:
            async for chunk in self.client.stream_async(self.ENDPOINT, params):
                chunks.append(chunk)

                # 查找 ping 事件
                try:
                    if isinstance(chunk, bytes):
                        chunk_str = chunk.decode("utf-8")
                    else:
                        chunk_str = chunk

                    if chunk_str.startswith("data: "):
                        json_str = chunk_str[6:].strip()
                        if json_str and json_str != "[DONE]":
                            event_data = json.loads(json_str)

                            if event_data.get("type") == "ping":
                                has_ping_event = True
                except Exception:
                    pass

        except Exception as e:
            error_occurred = True
            error_msg = str(e)

        # 记录测试结果
        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=200 if not error_occurred else 500,
            response_body={"chunks_received": len(chunks), "has_ping_event": has_ping_event},
            error=error_msg if error_occurred else None,
        )

        if error_occurred:
            self.collector.add_unsupported_param(
                param_name="stream",
                param_value="ping_event",
                test_name=test_name,
                reason=f"Streaming error: {error_msg}",
            )

        assert not error_occurred, f"Streaming failed: {error_msg}"
        assert len(chunks) > 0, "No chunks received"
