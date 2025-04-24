from llama_index.core.schema import NodeWithScore
from openai import AsyncOpenAI, NOT_GIVEN
from openai.types.chat import ChatCompletionMessageParam
from openai_messages_token_helper import count_tokens_for_message
from typing import AsyncGenerator, List, Optional
from dataclasses import dataclass
from crawlers.base import CrawlerResult, CrawlerMetadata
from rag.models import Knowledge, get_db_session
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_exponential
from agent.optimizer import Optimizer
import asyncio
from agent.analyzer import Analyzer
import json
import traceback

SYSTEM_PROMPT = (
    "You are a helpful assistant of The Chinese University of Hong Kong, Shenzhen (香港中文大学（深圳）) to help undergraduate students with their questions."
    "Questions are in undergraduate context by default."
    "You should answer the user's question based on the information you have."
    "You should not answer the user's question if you do not have the information."
    "You can provide the user with the possible contact information you have if the user's question is not related to the information you have."
    "Always use the same language as the user's question."
    "Reference Required: Summarize the valid information you have first, and then provide your answer step by step. "
    "You must use references in each sentence of your answer. You should ensure that every piece of information you provide is supported by a reference."
    "Reference in markdown format. "
    "You should list relevant content's url and title at the end of your answer except the user's question is not related to the information you have."
    "Ask the user to provide more information if the user's question is not clear."
    "The query used in run_query function ** MUST ** be in ** English **, except special terms or names in Chinese."
    "It would be better to separate the subjects into different queries when comparison is needed. (Parallel tool calls is supported.)"
    f"Today is {datetime.now().strftime('%Y-%m-%d')}."
)

MODEL = "gpt-4o-2024-08-06"
DEEP_THINKING_MODEL = "gpt-4o-2024-08-06"
MAX_LOOPS = 3
MAX_TOKENS = 16000  # 设置一个合理的上限
RESERVE_TOKENS = 1000  # 为模型回复预留的token数


def count_tokens(messages: list[ChatCompletionMessageParam] | str) -> int:
    """计算消息的 token 数量"""
    result = 0
    if isinstance(messages, str):
        result = count_tokens_for_message(
            MODEL, {"role": "user", "content": messages}, True
        )
    else:
        for m in messages:
            result += count_tokens_for_message(MODEL, m, True)
    return result


@dataclass
class QueryResult:
    query: str
    node_text: str
    results: List[CrawlerResult]
    nodes: Optional[List[NodeWithScore]] = None

    @staticmethod
    def from_multi_results(query_result_objs: list["QueryResult"]) -> "QueryResult":
        return QueryResult(
            query=" ".join([q.query for q in query_result_objs]),
            node_text="\n".join([q.node_text for q in query_result_objs]),
            results=list(set([r for q in query_result_objs for r in q.results])),
        )


@dataclass
class Reference:
    mimetype: str
    preview_url: str
    source: str
    title: str
    description: str

    @staticmethod
    def from_crawler_result(crawler_result: CrawlerResult) -> "Reference":
        return Reference(
            mimetype=crawler_result.mimetype,
            preview_url=crawler_result.metadata.url,
            source=crawler_result.metadata.source,
            title=crawler_result.metadata.title,
            # description=f"{crawler_result.content[:100]}..." if len(crawler_result.content) > 100 else crawler_result.content,
            description=crawler_result.content,
        )

    def __eq__(self, other: "Reference") -> bool:
        return self.preview_url == other.preview_url

    def __hash__(self) -> int:
        return hash(self.preview_url)


class Agent:
    def __init__(
        self,
        openai_client: AsyncOpenAI,
    ):
        self.openai_client = openai_client
        self.optimizer = Optimizer()

    async def build_message(
        self,
        messages: list[ChatCompletionMessageParam],
        related_messages: QueryResult = None,
        system_prompt: str = SYSTEM_PROMPT,
    ) -> List[dict]:
        """构建消息列表，包括系统提示和相关信息，并确保不超过token限制。

        Args:
            messages: 原始消息列表
            related_messages: 相关信息查询结果
            system_prompt: 系统提示内容

        Returns:
            构建后的消息列表
        """
        # 创建消息列表的副本，避免修改原始列表
        messages_copy = messages.copy()

        # 仅保留最近5轮对话
        # 首先分离系统消息和对话消息
        system_messages = [msg for msg in messages_copy if msg["role"] == "system"]
        dialog_messages = [msg for msg in messages_copy if msg["role"] != "system"]

        # 将对话按轮次分组 (用户+助手+工具消息构成一轮)
        conversation_turns = []
        current_turn = []

        for msg in dialog_messages:
            if msg["role"] == "user" and current_turn:
                # 新的用户消息表示新的一轮对话开始
                conversation_turns.append(current_turn)
                current_turn = [msg]
            else:
                current_turn.append(msg)

        # 添加最后一轮对话
        if current_turn:
            conversation_turns.append(current_turn)

        # 仅保留最近5轮对话
        if len(conversation_turns) > 5:
            print(f"对话轮数过多({len(conversation_turns)}>5)，仅保留最近5轮")
            conversation_turns = conversation_turns[-5:]

        # 重新构建消息列表
        messages_copy = system_messages.copy()
        for turn in conversation_turns:
            messages_copy.extend(turn)

        print(f"保留的对话轮数: {len(conversation_turns)}")

        hint = self.optimizer.optimize(messages_copy)

        # 准备系统消息
        system_message = {
            "role": "system",
            "content": system_prompt + hint,
        }

        # 准备相关信息消息(如果有)
        related_info_message = None
        if related_messages:
            related_info_message = {
                "role": "system",
                "content": f"|> Related information: {related_messages.node_text.strip()} <|",
            }

        # 1. 找到或替换系统消息
        system_index = -1
        related_info_index = -1

        for i, msg in enumerate(messages_copy):
            if msg["role"] == "system" and not msg.get("content", "").startswith(
                "|> Related information:"
            ):
                system_index = i
            elif msg["role"] == "system" and msg.get("content", "").startswith(
                "|> Related information:"
            ):
                related_info_index = i

        # 替换或添加系统消息
        if system_index >= 0:
            messages_copy[system_index] = system_message
        else:
            messages_copy.insert(0, system_message)

        # 暂时不添加related_info_message，先计算其他消息的token数

        # 2. 计算当前消息(不含related_info)的token数量
        base_tokens_count = count_tokens(messages_copy)
        print(f"基础消息token数: {base_tokens_count}")

        # 目标token总数上限
        target_tokens = MAX_TOKENS - RESERVE_TOKENS

        # 3. 计算可用于related_info的token数
        available_tokens = target_tokens - base_tokens_count
        print(f"可用于相关信息的token数: {available_tokens}")

        # 4. 如果有相关信息，裁剪并添加
        if related_info_message:
            related_info_tokens = count_tokens([related_info_message])

            if related_info_tokens > available_tokens and available_tokens > 100:
                # 需要裁剪相关信息
                print(
                    f"相关信息token数过多({related_info_tokens}>{available_tokens})，需要裁剪"
                )

                # 获取原始内容
                content = related_info_message["content"]

                # 估算需要保留的比例 (保守估计)
                keep_ratio = available_tokens / related_info_tokens

                # 裁剪内容 (简单按比例裁剪，实际应用中可能需要更复杂的裁剪逻辑)
                trim_length = int(len(content) * keep_ratio)
                if trim_length > 100:  # 确保至少保留一定长度
                    related_info_message["content"] = (
                        content[:trim_length] + "...(content trimmed due to length)"
                    )
                    print(
                        f"裁剪了相关信息，从 {related_info_tokens} tokens 减少到约 {count_tokens([related_info_message])} tokens"
                    )

            # 添加或替换相关信息消息
            if related_info_index >= 0:
                messages_copy[related_info_index] = related_info_message
            else:
                messages_copy.insert(1, related_info_message)  # 插入到系统消息之后

        # 5. 最终检查
        final_tokens = count_tokens(messages_copy)
        print(f"最终token数: {final_tokens}，保留消息数: {len(messages_copy)}")

        # 记录消息角色序列
        roles = [msg["role"] for msg in messages_copy]
        print(f"消息角色序列: {roles}")

        return messages_copy

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=15)
    )
    async def run(
        self, messages: list[ChatCompletionMessageParam], context: dict = None
    ) -> AsyncGenerator[dict, None]:
        if context is None:
            context = {}
        related_messages = None

        try:
            response = await self.openai_client.chat.completions.create(
                model=MODEL,
                messages=await self.build_message(
                    messages, related_messages, SYSTEM_PROMPT
                ),
                stream=True,
                tools=[
                    {
                        "type": "function",
                        "function": {
                            "name": "run_query",
                            "description": "Run a query to search information in the knowledge base.",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "query": {
                                        "type": "string",
                                        "description": "The query should be detail and concise without including school name.",
                                    },
                                    "keywords": {
                                        "type": "array",
                                        "description": "The related keywords to the query.",
                                        "items": {
                                            "type": "string",
                                        },
                                    },
                                },
                                "required": ["query", "keywords"],
                            },
                        },
                    }
                ],
                temperature=0,
                parallel_tool_calls=True,
            )

            is_first_chunk = True
            tool_calls: dict[int, dict[str, str | dict[str, str]]] = {}
            answer = ""
            async for chunk in response:
                # 除了首尾的 chunk，choices 字段都不为空
                if choices := chunk.choices:
                    if delta := choices[0].delta:
                        # 只有第一个 chunk 会存在 role 字段
                        # role 字段理论上一定为 "assistant" ?
                        if content := delta.content:
                            if is_first_chunk:
                                yield {"delta": {"role": "assistant"}}
                                is_first_chunk = False
                            # 存在 content 字段，说明不调用工具
                            answer += content
                            yield {"delta": {"content": content}}

                        if tool_calls_chunks := delta.tool_calls:
                            # 存在 tool_calls 字段，说明调用了工具
                            # 可能调用了多个工具
                            for tc in tool_calls_chunks:
                                # yield {"delta": {"tool_calls": [tc.to_dict()], "role": delta.role}}
                                if tool_calls.get(tc.index) is None:
                                    # 第一次调用工具，将工具调用信息加入 tools_to_call
                                    # TODO: 此处 index 顺序未知，需要确认
                                    tool_calls[tc.index] = {
                                        # OpenAI 文档规定了发回给模型的 tool_call 格式，
                                        # 为了方便，这里传给前端使用相同的格式
                                        # 格式要求：https://platform.openai.com/docs/guides/function-calling#tool-calling-behavior
                                        "id": tc.id,  # id 只会在第一次出现
                                        "type": "function",
                                        "index": tc.index,
                                        "function": {
                                            "name": tc.function.name or "",
                                            "arguments": tc.function.arguments or "",
                                        },
                                    }
                                else:
                                    # 第 x 次调用工具，将工具调用结果加入 tools_to_call
                                    tool_calls[tc.index]["function"]["name"] += (
                                        tc.function.name or ""
                                    )
                                    tool_calls[tc.index]["function"]["arguments"] += (
                                        tc.function.arguments or ""
                                    )

            if not tool_calls:
                context["answer"] = answer
                from api.models import UserRecord

                await UserRecord.objects.acreate(
                    user_id=context["user_id"] or "unknown",
                    messages=context["messages"] or [],
                    question=context["question"] or "",
                    query="",
                    nodes=[],
                    score=0,
                    answer=context["answer"] or "",
                )
                return

            # 调用工具
            tool_calls = filter(
                lambda x: x["function"]["name"] == "run_query", tool_calls.values()
            )
            tool_calls = list(tool_calls)
            yield {"delta": {"tool_calls": tool_calls, "role": "assistant"}}
            tasks = [
                self.run_query(
                    json.loads(tool_call["function"]["arguments"])["query"],
                    json.loads(tool_call["function"]["arguments"])["keywords"],
                    context,
                )
                for tool_call in tool_calls
                if tool_call["function"]["name"] == "run_query"
            ]
            context["query"] = " ".join(
                [tool_call["function"]["arguments"] for tool_call in tool_calls]
            )
            results: list[QueryResult] = await asyncio.gather(*tasks)
            query_result = QueryResult.from_multi_results(results)
            references = [
                Reference.from_crawler_result(r) for r in query_result.results
            ]

            # 去重
            references = list(set(references))

            yield {"delta": {"role": "assistant", "references": references}}

            # 生成最终答案
            response = await self.openai_client.chat.completions.create(
                model=MODEL,
                messages=await self.build_message(
                    messages, query_result, SYSTEM_PROMPT
                ),
                stream=True,
                temperature=0.3,
            )
            answer = ""
            async for chunk in response:
                # 除了首尾的 chunk，choices 字段都不为空
                if choices := chunk.choices:
                    if delta := choices[0].delta:
                        # 只有第一个 chunk 会存在 role 字段
                        # role 字段理论上一定为 "assistant" ?
                        if content := delta.content:
                            # 存在 content 字段，说明不调用工具
                            answer += content
                            yield {"delta": {"content": content}}

                        if finish_reason := choices[0].finish_reason:
                            # print(f'>>>>>>>>>>>>>>>>>>> [finish_reason]: {finish_reason}\n')
                            match finish_reason:
                                case "tool_calls":
                                    # called tools
                                    pass
                                case "stop":
                                    # hit a natural stop
                                    pass
                                case "length":
                                    # reached the maximum number of tokens specified in the request
                                    pass
                                case "content_filter":
                                    # was omitted due to the content filters
                                    # TODO
                                    pass
                                case _:
                                    raise Exception(
                                        f">>>>>>>>>>>>>>>>>>> [finish_reason]: {finish_reason}\n"
                                    )
                        else:  # delta := ChoiceDelta(content='', function_call=None, refusal=None, role='assistant', tool_calls=None)
                            # 最后一个 delta 是为空的
                            pass

            context["answer"] = answer

            from api.models import UserRecord

            await UserRecord.objects.acreate(
                user_id=context["user_id"] or "unknown",
                messages=context["messages"] or [],
                question=context["question"] or "",
                query=context["query"] or "",
                nodes=context["nodes"] or [],
                score=context["score"] or 0,
                answer=context["answer"] or "",
            )

        except Exception as e:
            traceback.print_exc()
            print(f">>>>>>>>>>>>>>>>>>> [error]: {e}")
            yield {
                "delta": {
                    "error": "An error occurred while processing your request. Please try again later."
                }
            }
            return

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=15)
    )
    async def run_deep(
        self, messages: list[ChatCompletionMessageParam], context: dict = None
    ) -> AsyncGenerator[dict, None]:
        if context is None:
            context = {}

        analyzer = Analyzer(self.openai_client)
        start_time = datetime.now()
        print(f">>>>>>>>>>>>>>>>>>> [analyzer]: start analyzing")
        kmds, context_query = await asyncio.gather(
            analyzer.analyze_kmds(messages), analyzer.analyze_context(messages)
        )
        end_time = datetime.now()
        print(
            f">>>>>>>>>>>>>>>>>>> [analyzer]: done analyzing, time: {end_time - start_time}\n"
        )
        keywords = kmds[0]
        multi_query = kmds[1]
        decomposition = kmds[2]
        step_back = kmds[3]

        print(f">>>>>>>>>>>>>>>>>>> [keywords]: {keywords}\n")
        print(f">>>>>>>>>>>>>>>>>>> [multi_query]: {multi_query}\n")
        print(f">>>>>>>>>>>>>>>>>>> [decomposition]: {decomposition}\n")
        print(f">>>>>>>>>>>>>>>>>>> [step_back]: {step_back}\n")
        print(f">>>>>>>>>>>>>>>>>>> [context_query]: {context_query}\n")

        tool_calls = [
            {"function": {"name": "run_query", "arguments": json.dumps({"query": k})}}
            for k in keywords + multi_query + decomposition + step_back
        ]
        yield {"delta": {"tool_calls": tool_calls}}

        context["query"] = "\n".join(keywords + multi_query + decomposition + step_back)

        initial_query_result: QueryResult = await self.run_query_batch(
            context_query,
            keywords + multi_query + decomposition + step_back + context_query,
            context,
        )
        references = [
            Reference.from_crawler_result(r) for r in initial_query_result.results
        ]
        references = list(set(references))
        context["nodes"] = initial_query_result.nodes

        yield {"delta": {"references": references}}

        context["references"] = references
        print(f">>>>>>>>>>>>>>>>>>> [deep_thinking]: start deep thinking")
        loop_count = 0

        # 复制初始messages作为工作副本
        working_messages = messages.copy()

        while loop_count < MAX_LOOPS:
            print(f">>>>>>>>>>>>>>>>>>> [deep_thinking]: loop {loop_count}")

            # 当前循环的query_result，首次使用初始查询结果，后续循环为None
            current_query_result = initial_query_result if loop_count == 0 else None

            response = await self.openai_client.chat.completions.create(
                model=DEEP_THINKING_MODEL,
                messages=await self.build_message(
                    working_messages, current_query_result, SYSTEM_PROMPT
                ),
                stream=True,
                tools=(
                    [
                        {
                            "type": "function",
                            "function": {
                                "name": "investigate_reference",
                                "description": "Read full text of the reference information.",
                                "parameters": {
                                    "type": "object",
                                    "properties": {
                                        "reference_index": {
                                            "type": "integer",
                                            "description": "Use this reference index to investigate the full"
                                            " text of the reference information.",
                                        }
                                    },
                                    "required": ["reference_index"],
                                },
                            },
                        }
                    ]
                    if loop_count < MAX_LOOPS - 1
                    else NOT_GIVEN
                ),
                temperature=0.3,
            )
            # 重置 query_result，避免下次循环时重复添加查询到的内容
            initial_query_result = None
            print(
                f">>>>>>>>>>>>>>>>>>> [deep_thinking]: tokens: {count_tokens(working_messages)}"
            )

            answer = ""
            tool_calls = {}
            async for chunk in response:
                if choices := chunk.choices:
                    if delta := choices[0].delta:
                        if content := delta.content:
                            answer += content
                            yield {"delta": {"content": content}}
                        if tool_calls_chunks := delta.tool_calls:
                            # 存在 tool_calls 字段，说明调用了工具
                            # 可能调用了多个工具
                            for tc in tool_calls_chunks:
                                # yield {"delta": {"tool_calls": [tc.to_dict()], "role": delta.role}}
                                if tool_calls.get(tc.index) is None:
                                    # 第一次调用工具，将工具调用信息加入 tools_to_call
                                    # TODO: 此处 index 顺序未知，需要确认
                                    tool_calls[tc.index] = {
                                        # OpenAI 文档规定了发回给模型的 tool_call 格式，
                                        # 为了方便，这里传给前端使用相同的格式
                                        # 格式要求：https://platform.openai.com/docs/guides/function-calling#tool-calling-behavior
                                        "id": tc.id,  # id 只会在第一次出现
                                        "type": "function",
                                        "index": tc.index,
                                        "function": {
                                            "name": tc.function.name or "",
                                            "arguments": tc.function.arguments or "",
                                        },
                                    }
                                else:
                                    # 第 x 次调用工具，将工具调用结果加入 tools_to_call
                                    tool_calls[tc.index]["function"]["name"] += (
                                        tc.function.name or ""
                                    )
                                    tool_calls[tc.index]["function"]["arguments"] += (
                                        tc.function.arguments or ""
                                    )

            # if tool_calls:
            #     yield {"delta": {"tool_calls": list(tool_calls.values()), "role": "assistant"}}

            for index, tc in tool_calls.items():
                if not tc["function"]["name"] == "investigate_reference":
                    continue
                print(
                    f'>>>>>>>>>>>>>>>>>>> [investigate_reference]: {tc["function"]["arguments"]}\n'
                )
                reference_index = json.loads(tc["function"]["arguments"])[
                    "reference_index"
                ]
                nodes = context["nodes"]
                if not nodes:
                    continue
                # print(list(set([node['reference_id'] for node in nodes])))
                if reference_index > len(nodes):
                    print(
                        f">>>>>>>>>>>>>>>>>>> [investigate_reference]: reference_index "
                        f"out of range: {reference_index} > {len(nodes)}\n"
                    )
                    continue
                node = nodes[reference_index - 1]

                if node:
                    yield {
                        "delta": {
                            "tool_calls": [
                                {
                                    "id": tc["id"],
                                    "type": "function",
                                    "function": {
                                        "name": tc["function"]["name"],
                                        "arguments": json.dumps(
                                            {
                                                "reference_id": node["title"],
                                            }
                                        ),
                                    },
                                }
                            ]
                        },
                        "role": "assistant",
                    }
                    # 添加到message中
                    working_messages.append(
                        {
                            "role": "assistant",
                            "tool_calls": [
                                {
                                    "id": tc["id"],
                                    "type": "function",
                                    "function": {
                                        "name": tc["function"]["name"],
                                        "arguments": tc["function"]["arguments"],
                                    },
                                }
                            ],
                        }
                    )
                    working_messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": f"|> Reference Full Content: {node['full_text'] if count_tokens(working_messages) < 10000 else node['text']} (Don't investigate the reference again)<|",
                        }
                    )
                else:
                    print(
                        f">>>>>>>>>>>>>>>>>>> [investigate_reference]: {reference_index} not found\n"
                    )

            if not tool_calls:
                break

            loop_count += 1

        try:
            from api.models import UserRecord

            await UserRecord.objects.acreate(
                user_id=context["user_id"] or "unknown",
                messages=working_messages or [],
                question=context["question"] or "",
                query=context["query"] or "",
                nodes=context["nodes"] or [],
                score=context["score"] or 0,
                answer=answer or "",
            )
        except Exception as e:
            traceback.print_exc()
            print(f">>>>>>>>>>>>>>>>>>> [error]: {e}")
            yield {
                "delta": {
                    "error": "An error occurred while processing your request. Please try again later."
                }
            }
            return

    async def run_query(
        self, query: str, keywords: list[str], context: dict = None
    ) -> QueryResult:
        from sds_ai_tutor.setup_env import get_rag

        if context is None:
            context = {}
        from sds_ai_tutor.setup_env import global_env

        print(f">>>>>>>>>>>>>>>>>>> [query]: {query} + {keywords}\n")
        start_time = datetime.now()
        rag = get_rag()
        main_query = query + f"Keywords: {', '.join(keywords)}"
        node_list: list[NodeWithScore] = await rag.retrieve(main_query)
        nodes = [node for node in node_list]
        if not nodes:
            print(f">>>>>>>>>>>>>>>>>>> [nodes is None]: {query}\n")
        [print(f">>>>>>>>>>>>>>>>>>> [node]: {node.score}\n") for node in nodes]
        ref_doc_ids = [node.node.ref_doc_id for node in nodes]
        # ref_doc_ids 去重，按照出现次数排序
        ref_doc_ids = sorted(
            set(ref_doc_ids), key=lambda x: ref_doc_ids.count(x), reverse=True
        )
        docs = await rag.query_documents(ref_doc_ids)
        session = get_db_session()
        results = {}
        for doc in docs:
            print(f">>>>>>>>>>>>>>>>>>> [doc]: {doc.id_}\n")
            knowledge = (
                session.query(Knowledge)
                .filter(Knowledge.raw_content_hash == doc.id_)
                .first()
            )
            if knowledge is None:
                print(f">>>>>>>>>>>>>>>>>>> [knowledge is None]: {doc.id_}\n")
                # 删除这个node
                nodes = [node for node in nodes if node.node.ref_doc_id != doc.id_]
                # 删除这个doc
                await rag.remove_document_by_id(doc.id_)
                continue
            results[doc.id_] = CrawlerResult(
                raw_data=knowledge.content,
                mimetype=knowledge.mimetype,
                content=knowledge.content,
                metadata=CrawlerMetadata(
                    title=knowledge.title,
                    date=knowledge.updated_at,
                    extra=knowledge.result_metadata,
                    source=knowledge.source,
                    url=knowledge.result_metadata["url"],
                ),
            )
        session.close()
        info_list = []
        for node in nodes:
            info = f"""url: {node.node.metadata['url']}
title: {node.node.metadata['title']}
{results[node.node.ref_doc_id].content
            if node.score > 0.8 and count_tokens(results[node.node.ref_doc_id].content) < 10000
            else node.node.text}
"""
            info_list.append(info)
        end_time = datetime.now()
        print(f">>>>>>>>>>>>>>>>>>> [query time]: {end_time - start_time}\n")
        if not info_list:
            context["nodes"] = []
            context["score"] = 0
            return QueryResult(
                query=query,
                node_text="No related information found.",
                results=[],
            )
        node_text = "\n\n".join(info_list)

        context["nodes"] = (
            [
                {
                    "url": node.node.metadata["url"],
                    "title": node.node.metadata["title"],
                    "score": node.score,
                    "text": info,
                }
                for node, info in zip(nodes, info_list)
            ]
            if nodes
            else []
        )
        context["score"] = (
            sum([node.score for node in nodes]) / len(nodes) if nodes else 0
        )

        return QueryResult(
            query=query,
            node_text=node_text,
            results=list(results.values()),
        )

    async def run_query_batch(
        self, main_queries: list[str], sub_queries: list[str], context: dict = None
    ) -> QueryResult:
        if context is None:
            context = {}
        from sds_ai_tutor.setup_env import get_rag

        # ================== retrieve ==================
        rag = get_rag()
        start_time = datetime.now()
        tasks = [rag.retrieve(query) for query in sub_queries]
        nodes_list: list[list[NodeWithScore]] = await asyncio.gather(*tasks)
        relevant_nodes = [node for node_list in nodes_list for node in node_list]
        # ================== rerank ==================
        reranked_nodes_list: list[NodeWithScore] = await rag.rerank(
            relevant_nodes, "\n".join(main_queries), cutoff=0.4
        )
        nodes_dict = {node.id_: node for node in reranked_nodes_list}
        nodes = list(nodes_dict.values())
        # ================== query documents ==================
        ref_doc_ids = [node.node.ref_doc_id for node in nodes]
        # ref_doc_ids 去重，按照出现次数排序
        ref_doc_ids = sorted(
            set(ref_doc_ids), key=lambda x: ref_doc_ids.count(x), reverse=True
        )
        docs = await rag.query_documents(ref_doc_ids)
        session = get_db_session()
        doc_ids = [doc.id_ for doc in docs]

        # ================== get knowledge ==================
        knowledge_list = (
            session.query(Knowledge)
            .filter(Knowledge.raw_content_hash.in_(doc_ids))
            .all()
        )
        session.close()
        # 删去找不到的knowledge
        knowledge_ids = [knowledge.raw_content_hash for knowledge in knowledge_list]
        empty_nodes = [
            node for node in nodes if node.node.ref_doc_id not in knowledge_ids
        ]
        for node in empty_nodes:
            print(
                f">>>>>>>>>>>>>>>>>>> [WARNING knowledge is None]: {node.node.ref_doc_id}\n"
            )
            nodes = [_n for _n in nodes if _n.node.ref_doc_id != node.node.ref_doc_id]
            await rag.remove_document_by_id(node.node.ref_doc_id)
        results = {
            knowledge.raw_content_hash: CrawlerResult(
                raw_data=knowledge.content,
                mimetype=knowledge.mimetype,
                content=knowledge.content,
                metadata=CrawlerMetadata(
                    title=knowledge.title,
                    date=knowledge.updated_at,
                    extra=knowledge.result_metadata,
                    source=knowledge.source,
                    url=knowledge.result_metadata["url"],
                ),
            )
            for knowledge in knowledge_list
        }
        # ================== generate info ==================
        info_list = []
        for i, node in enumerate(nodes):
            info = f"""# Reference {i+1}:
reference_index: {i+1}
url: {node.node.metadata['url']}
title: {node.node.metadata['title']}
{node.node.text}
"""
            info_list.append(info)
        end_time = datetime.now()
        print(f">>>>>>>>>>>>>>>>>>> [query time]: {end_time - start_time}\n")
        # ================== return ==================
        if not info_list:
            context["nodes"] = []
            context["score"] = 0
            return QueryResult(
                query=str(main_queries),
                node_text="No related information found.",
                results=[],
            )
        node_text = "\n\n".join(info_list)

        nodes = (
            [
                {
                    "reference_id": node.node.ref_doc_id,
                    "url": node.node.metadata["url"],
                    "title": node.node.metadata["title"],
                    "score": node.score,
                    "text": info,
                    "full_text": results[node.node.ref_doc_id].content,
                }
                for node, info in zip(nodes, info_list)
            ]
            if nodes
            else []
        )
        context["nodes"] = nodes
        context["score"] = (
            sum([node["score"] for node in nodes]) / len(nodes) if nodes else 0
        )

        return QueryResult(
            query=str(main_queries),
            node_text=node_text,
            results=list(results.values()),
            nodes=nodes,
        )
