"""
搜索模块视图
实现全文搜索、语义搜索和聊天问答功能
"""
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from django.core.paginator import Paginator

from src.backend.sitesearch.api.models import Site, SearchLog


def get_client_info(request):
    """获取客户端信息"""
    return {
        'user_ip': request.META.get('REMOTE_ADDR', ''),
        'user_agent': request.META.get('HTTP_USER_AGENT', '')
    }


def search(request):
    """
    全文搜索接口
    GET: 执行全文搜索，支持跨站点或特定站点搜索，支持分页和排序
    """
    try:
        # 获取查询参数
        query = request.GET.get('q', '')
        site_id = request.GET.get('site_id')
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 10))
        sort_by = request.GET.get('sort_by', 'relevance')  # relevance, date, title
        filter_mimetype = request.GET.get('mimetype')
        date_start = request.GET.get('date_start')
        date_end = request.GET.get('date_end')
        
        # 验证查询不为空
        if not query:
            return JsonResponse({'error': '搜索查询不能为空'}, status=400)
        
        # 验证站点ID (如果提供)
        if site_id:
            try:
                Site.objects.get(id=site_id)
            except Site.DoesNotExist:
                return JsonResponse({'error': f'站点不存在: {site_id}'}, status=400)
        
        # 记录搜索开始时间
        import time
        start_time = time.time()
        
        # 构建搜索过滤器
        filters = {}
        if site_id:
            filters['site_id'] = site_id
        if filter_mimetype:
            filters['mimetype'] = filter_mimetype
        if date_start:
            filters['created_at__gte'] = date_start
        if date_end:
            filters['created_at__lte'] = date_end
        
        # 从索引模块中导入搜索函数
        from src.backend.sitesearch.indexer.search import search_documents
        
        # 执行搜索
        search_results = search_documents(
            query=query,
            filters=filters,
            page=page,
            page_size=page_size,
            sort_by=sort_by
        )
        
        # 计算执行时间
        execution_time_ms = int((time.time() - start_time) * 1000)
        
        # 记录搜索日志
        client_info = get_client_info(request)
        search_log = SearchLog(
            query=query,
            search_type='fulltext',
            site_id=site_id,
            results_count=search_results.get('total_count', 0),
            execution_time_ms=execution_time_ms,
            user_ip=client_info['user_ip'],
            user_agent=client_info['user_agent'],
            filters=filters,
            result_ids=[r.get('id') for r in search_results.get('results', [])]
        )
        search_log.save()
        
        # 构建响应
        response = {
            'query': query,
            'results': search_results.get('results', []),
            'total_count': search_results.get('total_count', 0),
            'page': page,
            'page_size': page_size,
            'execution_time_ms': execution_time_ms,
            'filters': filters
        }
        
        return JsonResponse(response)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def semantic_search(request):
    """
    语义搜索接口
    GET: 执行语义搜索，支持自然语言查询和相关度排序
    """
    try:
        # 获取查询参数
        query = request.GET.get('q', '')
        site_id = request.GET.get('site_id')
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 5))
        filter_mimetype = request.GET.get('mimetype')
        
        # 验证查询不为空
        if not query:
            return JsonResponse({'error': '搜索查询不能为空'}, status=400)
        
        # 验证站点ID (如果提供)
        if site_id:
            try:
                Site.objects.get(id=site_id)
            except Site.DoesNotExist:
                return JsonResponse({'error': f'站点不存在: {site_id}'}, status=400)
        
        # 记录搜索开始时间
        import time
        start_time = time.time()
        
        # 构建搜索过滤器
        filters = {}
        if site_id:
            filters['site_id'] = site_id
        if filter_mimetype:
            filters['mimetype'] = filter_mimetype
        
        # 从索引模块中导入语义搜索函数
        from src.backend.sitesearch.indexer.search import semantic_search_documents
        
        # 执行搜索
        search_results = semantic_search_documents(
            query=query,
            filters=filters,
            top_k=page_size,
            page=page
        )
        
        # 计算执行时间
        execution_time_ms = int((time.time() - start_time) * 1000)
        
        # 记录搜索日志
        client_info = get_client_info(request)
        search_log = SearchLog(
            query=query,
            search_type='semantic',
            site_id=site_id,
            results_count=search_results.get('total_count', 0),
            execution_time_ms=execution_time_ms,
            user_ip=client_info['user_ip'],
            user_agent=client_info['user_agent'],
            filters=filters,
            result_ids=[r.get('id') for r in search_results.get('results', [])]
        )
        search_log.save()
        
        # 构建响应
        response = {
            'query': query,
            'results': search_results.get('results', []),
            'total_count': search_results.get('total_count', 0),
            'page': page,
            'page_size': page_size,
            'execution_time_ms': execution_time_ms,
            'filters': filters
        }
        
        return JsonResponse(response)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def chat(request):
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
                Site.objects.get(id=site_id)
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
        from src.backend.sitesearch.indexer.chat import generate_chat_response
        
        # 生成回答
        response_data = generate_chat_response(
            query=query,
            chat_history=chat_history,
            filters=filters
        )
        
        # 计算执行时间
        execution_time_ms = int((time.time() - start_time) * 1000)
        
        # 记录搜索日志
        client_info = get_client_info(request)
        search_log = SearchLog(
            query=query,
            search_type='chat',
            site_id=site_id,
            results_count=len(response_data.get('sources', [])),
            execution_time_ms=execution_time_ms,
            user_ip=client_info['user_ip'],
            user_agent=client_info['user_agent'],
            filters=filters,
            result_ids=[s.get('id') for s in response_data.get('sources', [])]
        )
        search_log.save()
        
        # 构建响应
        response = {
            'query': query,
            'response': response_data.get('response', ''),
            'sources': response_data.get('sources', []),
            'execution_time_ms': execution_time_ms
        }
        
        return JsonResponse(response)
        
    except json.JSONDecodeError:
        return JsonResponse({'error': '无效的JSON数据'}, status=400)
    except Exception as e:
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