"""
聊天服务
集成Agent、Analyzer和相关服务，提供统一的聊天接口
"""
import os
import json
import asyncio
from typing import Dict, List, Any, AsyncGenerator, Optional
from datetime import datetime

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam

from agent.model import Agent
from agent.analyzer import Analyzer

# 配置默认值
DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_DEEP_MODEL = "gpt-4o"

class ChatService:
    """聊天服务类
    
    提供对话、搜索等功能的统一接口，管理底层组件的实例化和交互
    """
    _instance = None
    
    @classmethod
    def get_instance(cls, config=None):
        """获取单例实例
        
        Args:
            config: 配置字典，用于覆盖默认配置
            
        Returns:
            ChatService实例
        """
        if cls._instance is None:
            cls._instance = ChatService(config)
        return cls._instance
    
    def __init__(self, config=None):
        """初始化聊天服务
        
        Args:
            config: 配置字典，用于覆盖默认配置
        """
        self.config = config or {}
        
        # 初始化OpenAI客户端
        self.openai_client = AsyncOpenAI(
            api_key=self.config.get("api_key") or os.getenv("OPENAI_API_KEY"),
            base_url=self.config.get("base_url") or os.getenv("OPENAI_BASE_URL")
        )
        
        # 初始化组件
        self.agent = Agent(
            self.openai_client,
            model=self.config.get("model", DEFAULT_MODEL),
            deep_thinking_model=self.config.get("deep_model", DEFAULT_DEEP_MODEL)
        )
        
        self.analyzer = Analyzer(
            self.openai_client,
            model=self.config.get("model", DEFAULT_MODEL)
        )
        
        # 维护会话记录
        self.sessions = {}
    
    async def chat(
        self, 
        messages: List[ChatCompletionMessageParam], 
        session_id: str = None,
        context: Dict[str, Any] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """基础聊天功能
        
        Args:
            messages: 聊天消息列表
            session_id: 会话ID，用于区分不同会话
            context: 上下文信息
            
        Yields:
            流式响应
        """
        if session_id:
            # 更新会话记录
            self.sessions[session_id] = {
                "last_active": datetime.now(),
                "messages": messages,
                "context": context or {}
            }
        
        # 使用Agent处理对话
        async for chunk in self.agent.run(messages, context):
            yield chunk
    
    async def chat_with_search(
        self, 
        messages: List[ChatCompletionMessageParam],
        search_function,
        session_id: str = None,
        context: Dict[str, Any] = None,
        deep_thinking: bool = False
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """带搜索功能的聊天
        
        Args:
            messages: 聊天消息列表
            search_function: 搜索函数，接收查询字符串返回结果
            session_id: 会话ID
            context: 上下文信息
            deep_thinking: 是否启用深度思考模式
            
        Yields:
            流式响应
        """
        if context is None:
            context = {}
        
        if session_id:
            # 更新会话记录
            self.sessions[session_id] = {
                "last_active": datetime.now(),
                "messages": messages,
                "context": context
            }
        
        # 提取最新的用户消息
        user_message = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                if isinstance(msg.get("content"), str):
                    user_message = msg.get("content")
                else:
                    parts = [p.get("text", "") for p in msg.get("content", []) if isinstance(p, dict)]
                    user_message = "".join(parts)
                break
        
        # 分析用户问题
        if deep_thinking:
            yield {"delta": {"content": "正在进行深度分析..."}}
            
            # 并行获取不同分析结果
            kmds_results = await self.analyzer.analyze_kmds(user_message)
            context_queries = await self.analyzer.analyze_context(user_message)
            
            # 展示分析结果
            yield {"delta": {"content": "\n正在搜索相关信息..."}}
            
            # 执行搜索查询
            search_queries = kmds_results[0] + kmds_results[1] + context_queries
            search_results = []
            
            for query in search_queries:
                try:
                    result = await search_function(query)
                    if result:
                        search_results.append(result)
                except Exception as e:
                    print(f"搜索查询失败: {query}, 错误: {e}")
            
            # 整合搜索结果
            if search_results:
                combined_results = "\n\n".join(search_results)
                
                # 添加搜索结果到消息中
                messages.append({
                    "role": "system",
                    "content": f"以下是与问题相关的信息:\n{combined_results}"
                })
                
                yield {"delta": {"content": "\n找到相关信息，正在生成回答..."}}
            else:
                yield {"delta": {"content": "\n未找到相关信息，将基于已有知识回答..."}}
        
        else:
            # 简单模式：直接使用用户消息进行搜索
            try:
                search_result = await search_function(user_message)
                if search_result:
                    # 添加搜索结果到消息中
                    messages.append({
                        "role": "system",
                        "content": f"以下是与问题相关的信息:\n{search_result}"
                    })
            except Exception as e:
                print(f"搜索查询失败，错误: {e}")
        
        # 使用Agent生成回答
        async for chunk in self.agent.run(messages, context):
            yield chunk
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话信息
        
        Args:
            session_id: 会话ID
            
        Returns:
            会话信息，如果会话不存在则返回None
        """
        return self.sessions.get(session_id)
    
    def clear_session(self, session_id: str) -> bool:
        """清除会话
        
        Args:
            session_id: 会话ID
            
        Returns:
            是否成功清除
        """
        if session_id in self.sessions:
            del self.sessions[session_id]
            return True
        return False
    
    def clear_expired_sessions(self, max_age_hours: int = 24) -> int:
        """清除过期会话
        
        Args:
            max_age_hours: 最大会话保存时间（小时）
            
        Returns:
            清除的会话数量
        """
        now = datetime.now()
        expired_sessions = []
        
        for session_id, session in self.sessions.items():
            age = (now - session["last_active"]).total_seconds() / 3600
            if age > max_age_hours:
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            del self.sessions[session_id]
            
        return len(expired_sessions) 