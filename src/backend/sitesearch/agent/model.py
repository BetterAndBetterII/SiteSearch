"""
Agent模型核心实现
"""
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam
from typing import AsyncGenerator, Dict, List, Any, Optional, Union
import json
import asyncio
import traceback
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_exponential

from src.backend.sitesearch.agent.optimizer import Optimizer

# 默认设置
MODEL = "gpt-4o-mini"
DEEP_THINKING_MODEL = "gpt-4o"
MAX_LOOPS = 3
MAX_TOKENS = 16000
RESERVE_TOKENS = 1000

# 系统提示词模板
SYSTEM_PROMPT = """
你是一个专业的智能助手，能够回答用户的各种问题。
尽可能给出准确和有帮助的回答。
如果需要更多信息才能回答问题，请明确告诉用户。
回答问题时要使用用户提问的语言。
今天是{date}。
"""

class Agent:
    """Agent核心类，负责与LLM交互并处理对话流程"""
    
    def __init__(
        self,
        openai_client: AsyncOpenAI,
        model: str = MODEL,
        deep_thinking_model: str = DEEP_THINKING_MODEL,
        system_prompt: str = SYSTEM_PROMPT,
        max_tokens: int = MAX_TOKENS,
        reserve_tokens: int = RESERVE_TOKENS,
    ):
        """初始化Agent
        
        Args:
            openai_client: OpenAI API客户端
            model: 默认使用的模型
            deep_thinking_model: 深度思考模式使用的模型
            system_prompt: 系统提示词模板
            max_tokens: 最大token数
            reserve_tokens: 保留token数
        """
        self.openai_client = openai_client
        self.model = model
        self.deep_thinking_model = deep_thinking_model
        self.system_prompt = system_prompt.format(date=datetime.now().strftime('%Y-%m-%d'))
        self.max_tokens = max_tokens
        self.reserve_tokens = reserve_tokens
        self.optimizer = Optimizer()
    
    async def build_message(
        self, 
        messages: List[ChatCompletionMessageParam],
        related_info: str = None
    ) -> List[ChatCompletionMessageParam]:
        """构建发送给模型的消息列表
        
        Args:
            messages: 原始消息列表
            related_info: 相关信息
            
        Returns:
            处理后的消息列表
        """
        # 创建消息列表的副本，避免修改原始列表
        messages_copy = messages.copy()
        
        # 获取专业术语提示
        hint = self.optimizer.optimize(messages_copy)
        
        # 系统提示词
        system_message = {
            "role": "system",
            "content": self.system_prompt + hint
        }
        
        # 查找或替换系统消息
        system_index = -1
        for i, msg in enumerate(messages_copy):
            if msg.get("role") == "system":
                system_index = i
                break
        
        if system_index >= 0:
            messages_copy[system_index] = system_message
        else:
            messages_copy.insert(0, system_message)
        
        # 添加相关信息（如果有）
        if related_info:
            messages_copy.append({
                "role": "system",
                "content": f"以下是与用户问题相关的信息:\n{related_info}"
            })
        
        return messages_copy
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=15))
    async def run(
        self, 
        messages: List[ChatCompletionMessageParam],
        context: Dict[str, Any] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """运行Agent进行基础对话
        
        Args:
            messages: 对话消息列表
            context: 可选的上下文信息
            
        Yields:
            流式响应
        """
        if context is None:
            context = {}
            
        try:
            # 准备消息
            prepared_messages = await self.build_message(messages)
            
            # 调用模型
            response = await self.openai_client.chat.completions.create(
                model=self.model,
                messages=prepared_messages,
                stream=True,
                temperature=0.7,
            )
            
            # 流式返回
            is_first_chunk = True
            async for chunk in response:
                if choices := chunk.choices:
                    if delta := choices[0].delta:
                        if role := delta.role:
                            if is_first_chunk:
                                yield {"delta": {"role": role}}
                                is_first_chunk = False
                        
                        if content := delta.content:
                            yield {"delta": {"content": content}}
            
        except Exception as e:
            traceback.print_exc()
            print(f"Agent运行错误: {e}")
            yield {
                "delta": {
                    "error": f"处理请求时出错: {str(e)}"
                }
            }
    
    async def run_with_tools(
        self,
        messages: List[ChatCompletionMessageParam],
        tools: List[Dict[str, Any]],
        tool_handlers: Dict[str, callable],
        context: Dict[str, Any] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """使用工具运行Agent
        
        Args:
            messages: 对话消息列表
            tools: 工具定义列表
            tool_handlers: 工具处理函数字典，键为工具名称
            context: 可选的上下文信息
            
        Yields:
            流式响应
        """
        if context is None:
            context = {}
            
        try:
            # 准备消息
            prepared_messages = await self.build_message(messages)
            
            # 调用模型
            response = await self.openai_client.chat.completions.create(
                model=self.model,
                messages=prepared_messages,
                stream=True,
                tools=tools,
                temperature=0.7,
            )
            
            # 处理流式响应
            is_first_chunk = True
            tool_calls = {}
            answer = ""
            
            async for chunk in response:
                if choices := chunk.choices:
                    if delta := choices[0].delta:
                        # 只有第一个chunk会包含role
                        if is_first_chunk:
                            yield {"delta": {"role": "assistant"}}
                            is_first_chunk = False
                        
                        # 处理文本内容
                        if content := delta.content:
                            answer += content
                            yield {"delta": {"content": content}}
                        
                        # 处理工具调用
                        if tool_calls_chunks := delta.tool_calls:
                            for tc in tool_calls_chunks:
                                if tool_calls.get(tc.index) is None:
                                    # 首次收到该工具调用
                                    tool_calls[tc.index] = {
                                        "id": tc.id,
                                        "type": "function",
                                        "index": tc.index,
                                        "function": {
                                            "name": tc.function.name or "",
                                            "arguments": tc.function.arguments or "",
                                        },
                                    }
                                else:
                                    # 继续接收工具调用信息
                                    tool_calls[tc.index]["function"]["name"] += tc.function.name or ""
                                    tool_calls[tc.index]["function"]["arguments"] += tc.function.arguments or ""
            
            # 如果没有工具调用，直接返回
            if not tool_calls:
                return
                
            # 通知前端工具调用
            tool_calls_list = list(tool_calls.values())
            yield {"delta": {"tool_calls": tool_calls_list}}
            
            # 执行工具调用
            tool_results = []
            for tool_call in tool_calls_list:
                tool_name = tool_call["function"]["name"]
                if tool_name in tool_handlers:
                    try:
                        arguments = json.loads(tool_call["function"]["arguments"])
                        result = await tool_handlers[tool_name](**arguments)
                        tool_results.append({
                            "tool_call_id": tool_call["id"],
                            "role": "tool",
                            "name": tool_name,
                            "content": result
                        })
                    except Exception as e:
                        tool_results.append({
                            "tool_call_id": tool_call["id"],
                            "role": "tool",
                            "name": tool_name,
                            "content": f"工具调用失败: {str(e)}"
                        })
            
            # 将工具结果添加到消息中
            for result in tool_results:
                messages.append({
                    "role": "assistant",
                    "tool_calls": [{
                        "id": result["tool_call_id"],
                        "type": "function",
                        "function": {
                            "name": result["name"],
                            "arguments": tool_calls_list[0]["function"]["arguments"]
                        }
                    }]
                })
                messages.append({
                    "role": "tool",
                    "tool_call_id": result["tool_call_id"],
                    "content": result["content"]
                })
            
            # 再次调用模型生成最终回答
            final_response = await self.openai_client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True,
                temperature=0.7,
            )
            
            async for chunk in final_response:
                if choices := chunk.choices:
                    if delta := choices[0].delta:
                        if content := delta.content:
                            yield {"delta": {"content": content}}
                    
        except Exception as e:
            traceback.print_exc()
            print(f"工具调用错误: {e}")
            yield {
                "delta": {
                    "error": f"处理工具调用时出错: {str(e)}"
                }
            } 