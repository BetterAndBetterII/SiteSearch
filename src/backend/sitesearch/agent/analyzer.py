# 关键词提取 多查询 分解 回溯
import os
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam
from tenacity import retry, stop_after_attempt, wait_exponential
import asyncio
from dotenv import load_dotenv
from enum import Enum
from datetime import datetime

load_dotenv()

MODEL = "gpt-4o-mini"  # 默认使用较小模型，可以通过参数覆盖
ITEM_COUNT = 3

class AnalyzerPrompt(Enum):
    CONTEXT_PROMPT = """You are a helpful assistant to help users with their questions.
        Questions are in user context by default.
        You are a helpful assistant that can use {ITEM_COUNT} query sentence(s) to describe the user's question in different ways.
        You should only return the {ITEM_COUNT} query sentences separated by newlines.
    """ + f"Today is {datetime.now().strftime('%Y-%m-%d')}."

    KEYWORDS_PROMPT = """You are a helpful assistant to help users with their questions.
        Questions are in user context by default.
        You are a helpful assistant that can extract keywords and relevant words from user's question.
        You should extract in both Chinese and English for each keyword.
        You should only return the {ITEM_COUNT} keywords separated by newlines.
    """ + f"Today is {datetime.now().strftime('%Y-%m-%d')}."

    MULTY_QUERY_PROMPT = """You are a helpful assistant to help users with their questions.
        Questions are in user context by default.
        You are an AI language model assistant. Your task is to generate {ITEM_COUNT} 
        different versions of the given user question to retrieve relevant documents from a vector 
        database. By generating multiple perspectives on the user question, your goal is to help
        the user overcome some of the limitations of the distance-based similarity search. 
        Provide these alternative questions separated by newlines.
    """ + f"Today is {datetime.now().strftime('%Y-%m-%d')}."

    DECOMPOSITION_PROMPT = """You are a helpful assistant to help users with their questions.
        Questions are in user context by default.
        You are a helpful assistant that generates {ITEM_COUNT} sub-questions related to an input question. \n
        The goal is to break down the input into a set of sub-problems / sub-questions that can be answers in isolation. \n
        Provide these alternative questions separated by newlines.
    """ + f"Today is {datetime.now().strftime('%Y-%m-%d')}."

    STEP_BACK_PROMPT = """You are a helpful assistant to help users with their questions.
        Questions are in user context by default.
        You are an expert at world knowledge. Your task is to step back and 
        paraphrase a question to more generic step-back questions, which are easier to answer.
        Provide {ITEM_COUNT} step-back questions separated by newlines.
    """ + f"Today is {datetime.now().strftime('%Y-%m-%d')}."

class Analyzer:
    def __init__(
        self,
        openai_client: AsyncOpenAI,
        model=MODEL,
    ):
        self.openai_client = openai_client
        self.model = model

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=15))
    async def analyze(self, messages: list[ChatCompletionMessageParam] | str, prompt: AnalyzerPrompt, item_count: int = ITEM_COUNT) -> list[str]:
        try:
            # 处理输入，如果是字符串，转换为消息列表
            if isinstance(messages, str):
                message_content = messages
                messages = [{"role": "user", "content": message_content}]
            
            response = await self.openai_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": [
                        {"type": "text", "text": ("You are a helpful assistant that can output items line by line. "
                                                  "You must output the items in the format of 'item1\nitem2\nitem3'. "
                                                  "Do not include any other text, numbering, or formatting."
                                                  )},
                        {"type": "text", "text": prompt.value.format(ITEM_COUNT=item_count)},
                    ]},
                    *messages
                ],
                max_tokens=1024,
                temperature=0
            )
            results = response.choices[0].message.content.split("\n")
            return [result.strip() for result in results if result.strip()]
        except Exception as e:
            print("Analyzer Error: ", e)
            return []
        
    async def analyze_kmds(self, message: str | list[ChatCompletionMessageParam], item_count: int = ITEM_COUNT) -> list[list[str]]:
        """并行执行关键词提取、多角度查询、问题分解和回溯分析
        
        Args:
            message: 用户消息文本或消息列表
            item_count: 每种分析返回的项目数量
            
        Returns:
            四种分析结果的列表: [keywords, multi_query, decomposition, step_back]
        """
        tasks = [
            self.analyze(message, AnalyzerPrompt.KEYWORDS_PROMPT, item_count),
            self.analyze(message, AnalyzerPrompt.MULTY_QUERY_PROMPT, item_count),
            self.analyze(message, AnalyzerPrompt.DECOMPOSITION_PROMPT, item_count),
            self.analyze(message, AnalyzerPrompt.STEP_BACK_PROMPT, item_count),
        ]
        return await asyncio.gather(*tasks)
    
    async def analyze_context(self, message: str | list[ChatCompletionMessageParam], item_count: int = 3) -> list[str]:
        """分析上下文，生成上下文查询
        
        Args:
            message: 用户消息文本或消息列表
            item_count: 返回的上下文查询数量
            
        Returns:
            上下文查询列表
        """
        return await self.analyze(message, AnalyzerPrompt.CONTEXT_PROMPT, item_count) 