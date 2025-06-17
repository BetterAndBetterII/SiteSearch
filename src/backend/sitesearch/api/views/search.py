"""
搜索模块视图
实现全文搜索、语义搜索和聊天问答功能
"""
from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
import json
import asyncio
import os
from django.core.paginator import Paginator
import traceback
import uuid
import logging

from src.backend.sitesearch.api.models import Site, SearchLog
from src.backend.sitesearch.agent.chat_service import ChatService

# 添加性能监控日志配置
logger = logging.getLogger(__name__)

def get_client_info(request):
    """获取客户端信息"""
    return {
        'user_ip': request.META.get('REMOTE_ADDR', ''),
        'user_agent': request.META.get('HTTP_USER_AGENT', '')
    }

async def format_ndjson(response_data):
    async for chunk in response_data:
        yield json.dumps(chunk) + '\n'


# def search(request):
#     """
#     全文搜索接口
#     GET: 执行全文搜索，支持跨站点或特定站点搜索，支持分页和排序
#     """
#     try:
#         # 获取查询参数
#         query = request.GET.get('q', '')
#         site_id = request.GET.get('site_id')
#         page = int(request.GET.get('page', 1))
#         page_size = int(request.GET.get('page_size', 10))
#         sort_by = request.GET.get('sort_by', 'relevance')  # relevance, date, title
#         filter_mimetype = request.GET.get('mimetype')
#         date_start = request.GET.get('date_start')
#         date_end = request.GET.get('date_end')
        
#         # 验证查询不为空
#         if not query:
#             return JsonResponse({'error': '搜索查询不能为空'}, status=400)
        
#         # 验证站点ID (如果提供)
#         if site_id:
#             try:
#                 Site.objects.get(id=site_id)
#             except Site.DoesNotExist:
#                 return JsonResponse({'error': f'站点不存在: {site_id}'}, status=400)
        
#         # 记录搜索开始时间
#         import time
#         start_time = time.time()
        
#         # 构建搜索过滤器
#         filters = {}
#         if site_id:
#             filters['site_id'] = site_id
#         if filter_mimetype:
#             filters['mimetype'] = filter_mimetype
#         if date_start:
#             filters['created_at__gte'] = date_start
#         if date_end:
#             filters['created_at__lte'] = date_end
        
#         # 从索引模块中导入搜索函数
#         from src.backend.sitesearch.indexer.search import search_documents
        
#         # 执行搜索
#         search_results = search_documents(
#             query=query,
#             filters=filters,
#             page=page,
#             page_size=page_size,
#             sort_by=sort_by
#         )
        
#         # 计算执行时间
#         execution_time_ms = int((time.time() - start_time) * 1000)
        
#         # 记录搜索日志
#         client_info = get_client_info(request)
#         search_log = SearchLog(
#             query=query,
#             search_type='fulltext',
#             site_id=site_id,
#             results_count=search_results.get('total_count', 0),
#             execution_time_ms=execution_time_ms,
#             user_ip=client_info['user_ip'],
#             user_agent=client_info['user_agent'],
#             filters=filters,
#             result_ids=[r.get('id') for r in search_results.get('results', [])]
#         )
#         search_log.save()
        
#         # 构建响应
#         response = {
#             'query': query,
#             'results': search_results.get('results', []),
#             'total_count': search_results.get('total_count', 0),
#             'page': page,
#             'page_size': page_size,
#             'execution_time_ms': execution_time_ms,
#             'filters': filters
#         }
        
#         return JsonResponse(response)
        
#     except Exception as e:
#         return JsonResponse({'error': str(e)}, status=500)


async def semantic_search(request):
    """
    语义搜索接口
    GET: 执行语义搜索，支持自然语言查询和相关度排序
    """
    # 记录总体开始时间
    import time
    total_start_time = time.time()
    performance_metrics = {}
    
    try:
        # 阶段1: 参数解析和验证
        parse_start_time = time.time()
        
        # 获取查询参数
        query = request.GET.get('q', '')
        site_id = request.GET.get('site_id')
        page = int(request.GET.get('page', 1))
        top_k = int(request.GET.get('top_k', 5))
        filter_mimetype = request.GET.get('mimetype')
        similarity_cutoff = float(request.GET.get('similarity_cutoff', 0.6))
        rerank = str(request.GET.get('rerank', 'True')).lower() == 'true'
        rerank_top_k = int(request.GET.get('rerank_top_k', 10))

        logger.info(f"Semantic Search - Query: '{query}' | Site: {site_id} | Page: {page} | Top K: {top_k} | Filter Mimetype: {filter_mimetype} | Similarity Cutoff: {similarity_cutoff} | Rerank: {rerank} | Rerank Top K: {rerank_top_k}")
        
        # 验证查询不为空
        if not query:
            return JsonResponse({'error': '搜索查询不能为空'}, status=400)
        
        performance_metrics['parse_params'] = (time.time() - parse_start_time) * 1000
        
        # 阶段2: 站点验证
        site_validation_start_time = time.time()
        
        # 验证站点ID (如果提供)
        site_ids = []
        if site_id:
            try:
                await Site.objects.aget(id=site_id)
            except Site.DoesNotExist:
                return JsonResponse({'error': f'站点不存在: {site_id}'}, status=400)
        else:
            site_ids = [site.id async for site in Site.objects.all()]
        
        performance_metrics['site_validation'] = (time.time() - site_validation_start_time) * 1000
        
        # 阶段3: 构建搜索过滤器
        filter_build_start_time = time.time()
        
        # 构建搜索过滤器
        filters = {}
        if site_id:
            filters['site_id'] = site_id
        if site_ids:
            filters['site_ids'] = site_ids
        if filter_mimetype:
            filters['mimetype'] = filter_mimetype
        
        performance_metrics['build_filters'] = (time.time() - filter_build_start_time) * 1000
        
        # 阶段4: 执行语义搜索
        search_start_time = time.time()
        
        # 从索引模块中导入语义搜索函数
        from src.backend.sitesearch.indexer.search import semantic_search_documents
        
        # 执行搜索
        search_results = await semantic_search_documents(
            query=query,
            filters=filters,
            top_k=top_k,
            page=page,
            similarity_cutoff=similarity_cutoff,
            rerank=rerank,
            rerank_top_k=rerank_top_k
        )
        
        performance_metrics['semantic_search'] = (time.time() - search_start_time) * 1000
        
        # 阶段5: 记录搜索日志
        logging_start_time = time.time()
        
        # 计算总执行时间
        total_execution_time_ms = int((time.time() - total_start_time) * 1000)
        
        # 记录搜索日志
        client_info = get_client_info(request)
        search_log = SearchLog(
            query=query,
            search_type='semantic',
            site_id=site_id,
            results_count=search_results.get('total_count', 0),
            execution_time_ms=total_execution_time_ms,
            user_ip=client_info['user_ip'],
            user_agent=client_info['user_agent'],
            filters=filters,
            result_ids=[r.get('id') for r in search_results.get('results', [])]
        )
        await search_log.asave()
        
        performance_metrics['logging'] = (time.time() - logging_start_time) * 1000
        
        # 阶段6: 构建响应
        response_build_start_time = time.time()
        
        # 构建响应
        response = {
            'query': query,
            'results': search_results.get('results', []),
            'total_count': search_results.get('total_count', 0),
            'page': page,
            'top_k': top_k,
            'execution_time_ms': total_execution_time_ms,
            'filters': filters
        }
        
        performance_metrics['build_response'] = (time.time() - response_build_start_time) * 1000
        performance_metrics['total'] = total_execution_time_ms
        
        # 输出详细性能日志
        logger.info(f"Semantic Search Performance Metrics - Query: '{query}' | Site: {site_id}")
        logger.info(f"  ├─ Parse Parameters: {performance_metrics['parse_params']:.2f}ms")
        logger.info(f"  ├─ Site Validation: {performance_metrics['site_validation']:.2f}ms")
        logger.info(f"  ├─ Build Filters: {performance_metrics['build_filters']:.2f}ms")
        logger.info(f"  ├─ Semantic Search: {performance_metrics['semantic_search']:.2f}ms")
        logger.info(f"  ├─ Logging: {performance_metrics['logging']:.2f}ms")
        logger.info(f"  ├─ Build Response: {performance_metrics['build_response']:.2f}ms")
        logger.info(f"  └─ Total Execution: {performance_metrics['total']:.2f}ms")
        logger.info(f"Results: {search_results.get('total_count', 0)} documents found")
        
        # 计算各阶段占比
        if total_execution_time_ms > 0:
            logger.info("Performance Breakdown:")
            logger.info(f"  ├─ Search Phase: {(performance_metrics['semantic_search']/performance_metrics['total']*100):.1f}%")
            logger.info(f"  ├─ Validation Phase: {(performance_metrics['site_validation']/performance_metrics['total']*100):.1f}%")
            logger.info(f"  ├─ Logging Phase: {(performance_metrics['logging']/performance_metrics['total']*100):.1f}%")
            logger.info(f"  └─ Other Phases: {((performance_metrics['parse_params']+performance_metrics['build_filters']+performance_metrics['build_response'])/performance_metrics['total']*100):.1f}%")
        
        return JsonResponse(response)
        
    except Exception as e:
        total_error_time = (time.time() - total_start_time) * 1000
        logger.error(f"Semantic Search Error after {total_error_time:.2f}ms - Query: '{query if 'query' in locals() else 'N/A'}' | Error: {str(e)}")
        logger.error(f"Error traceback: {traceback.format_exc()}")
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
async def chat(request):
    """
    基于已索引内容的对话问答接口
    POST: 处理用户问题并返回基于索引内容的回答
    """
    if request.method != 'POST':
        return JsonResponse({'error': '不支持的请求方法'}, status=405)
    
    try:
        # 解析请求体
        data = json.loads(request.body)
        
        # 获取必要参数
        query = data.get('query', '')
        site_id = data.get('site_id')
        chat_history = data.get('chat_history', [])
        
        # 验证查询不为空
        if not query:
            return JsonResponse({'error': '问题不能为空'}, status=400)
        
        # 验证站点ID (如果提供)
        if site_id:
            try:
                await Site.objects.aget(id=site_id)
            except Site.DoesNotExist:
                return JsonResponse({'error': f'站点不存在: {site_id}'}, status=400)
        
        # 记录搜索开始时间
        import time
        start_time = time.time()
        
        # 构建搜索过滤器
        filters = {}
        if site_id:
            filters['site_id'] = site_id
        
        # 从索引模块中导入聊天问答函数
        from src.backend.sitesearch.agent.chat_service import ChatService
        
        # 生成回答
        response_data = ChatService.get_instance().chat(
            messages=chat_history,
            site_id=site_id,
            session_id=uuid.uuid4().hex
        )
        
        # 计算执行时间
        execution_time_ms = int((time.time() - start_time) * 1000)
        
        # 记录搜索日志
        # client_info = get_client_info(request)
        # search_log = SearchLog(
        #     query=query,
        #     search_type='chat',
        #     site_id=site_id,
        #     results_count=len(response_data.get('sources', [])),
        #     execution_time_ms=execution_time_ms,
        #     user_ip=client_info['user_ip'],
        #     user_agent=client_info['user_agent'],
        #     filters=filters,
        #     result_ids=[s.get('id') for s in response_data.get('sources', [])]
        # )
        # search_log.save()
        
        # # 构建响应
        # response = {
        #     'query': query,
        #     'response': response_data.get('response', ''),
        #     'sources': response_data.get('sources', []),
        #     'execution_time_ms': execution_time_ms
        # }
        
        # return JsonResponse(response)
        return StreamingHttpResponse(format_ndjson(response_data), content_type='application/x-ndjson+json')
        
    except json.JSONDecodeError:
        return JsonResponse({'error': '无效的JSON数据'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def ai_chat(request):
    """
    AI智能聊天接口 (流式响应)
    POST: 处理用户问题并返回来自AI的流式回答
    """
    if request.method != 'POST':
        return JsonResponse({'error': '不支持的请求方法'}, status=405)
    
    try:
        # 解析请求体
        data = json.loads(request.body)
        
        # 获取必要参数
        messages = data.get('messages', [])
        session_id = data.get('session_id')
        deep_thinking = data.get('deep_thinking', False)
        site_id = data.get('site_id')
        
        # 验证消息不为空
        if not messages or len(messages) == 0:
            return JsonResponse({'error': '消息不能为空'}, status=400)
        
        # 提取用户最新问题
        last_message = ""
        for msg in reversed(messages):
            if msg.get('role') == 'user':
                if isinstance(msg.get('content'), str):
                    last_message = msg.get('content')
                else:
                    parts = [p.get('text', '') for p in msg.get('content', []) if isinstance(p, dict)]
                    last_message = "".join(parts)
                break
                
        if not last_message:
            return JsonResponse({'error': '未找到用户问题'}, status=400)
        
        # 验证站点ID (如果提供)
        if site_id:
            try:
                Site.objects.get(id=site_id)
            except Site.DoesNotExist:
                return JsonResponse({'error': f'站点不存在: {site_id}'}, status=400)
                
        # 记录开始搜索
        import time
        start_time = time.time()
        
        # 构建上下文信息
        context = {
            'user_id': session_id or 'anonymous',
            'site_id': site_id,
            'question': last_message,
            'messages': messages,
        }
        
        # 获取ChatService实例
        chat_service = ChatService.get_instance({
            'api_key': os.getenv('OPENAI_API_KEY'),
            'base_url': os.getenv('OPENAI_BASE_URL'),
            'model': os.getenv('OPENAI_MODEL', 'gpt-4o-mini'),
            'deep_model': os.getenv('OPENAI_DEEP_MODEL', 'gpt-4o')
        })
        
        # 创建搜索函数
        async def search_function(query):
            """根据查询获取搜索结果"""
            from src.backend.sitesearch.indexer.search import semantic_search_documents
            
            filters = {}
            if site_id:
                filters['site_id'] = site_id
                
            # 执行语义搜索
            results = semantic_search_documents(
                query=query,
                filters=filters,
                top_k=5
            )
            
            # 提取内容并格式化
            formatted_results = []
            for result in results.get('results', []):
                formatted_results.append(
                    f"来源: {result.get('title')}\n"
                    f"URL: {result.get('url')}\n"
                    f"内容: {result.get('content')}\n"
                )
                
            # 如果有结果，返回格式化的文本
            if formatted_results:
                return "\n\n".join(formatted_results)
            return None
        
        # 创建流式响应函数
        async def stream_response():
            try:
                # 根据deep_thinking选择使用哪个方法
                if deep_thinking:
                    async_gen = chat_service.chat_with_search(
                        messages=messages,
                        search_function=search_function,
                        session_id=session_id,
                        context=context,
                        deep_thinking=True
                    )
                else:
                    async_gen = chat_service.chat_with_search(
                        messages=messages,
                        search_function=search_function,
                        session_id=session_id,
                        context=context,
                        deep_thinking=False
                    )
                    
                # 流式返回结果
                async for chunk in async_gen:
                    yield f"data: {json.dumps(chunk)}\n\n"
                    
                # 计算处理时间并记录日志
                execution_time_ms = int((time.time() - start_time) * 1000)
                
                # 记录搜索日志
                client_info = get_client_info(request)
                search_log = SearchLog(
                    query=last_message,
                    search_type='ai_chat',
                    site_id=site_id,
                    results_count=0,  # 这里无法准确获取结果数量
                    execution_time_ms=execution_time_ms,
                    user_ip=client_info['user_ip'],
                    user_agent=client_info['user_agent'],
                    filters={'deep_thinking': deep_thinking}
                )
                search_log.save()
                
            except Exception as e:
                import traceback
                traceback.print_exc()
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                
        # 创建流式响应
        response = StreamingHttpResponse(
            streaming_content=asyncio.run(stream_response()),
            content_type='text/event-stream'
        )
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        
        return response
        
    except json.JSONDecodeError:
        return JsonResponse({'error': '无效的JSON数据'}, status=400)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def search_feedback(request, search_log_id):
    """
    记录用户对搜索结果的反馈
    POST: 更新搜索日志中的用户反馈
    """
    if request.method != 'POST':
        return JsonResponse({'error': '不支持的请求方法'}, status=405)
    
    try:
        # 解析请求体
        data = json.loads(request.body)
        
        # 获取反馈值 (-1: 不满意, 0: 中立, 1: 满意)
        feedback = data.get('feedback')
        
        # 验证反馈值
        if feedback not in (-1, 0, 1):
            return JsonResponse({'error': '无效的反馈值，应为-1、0或1'}, status=400)
        
        # 查找搜索日志
        try:
            search_log = SearchLog.objects.get(id=search_log_id)
        except SearchLog.DoesNotExist:
            return JsonResponse({'error': f'搜索日志不存在: {search_log_id}'}, status=404)
        
        # 更新反馈
        search_log.user_feedback = feedback
        search_log.save()
        
        return JsonResponse({
            'message': '感谢您的反馈',
            'search_log_id': search_log_id,
            'feedback': feedback
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': '无效的JSON数据'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500) 