"""
文档管理模块视图
实现站点文档的查询和刷新功能
"""
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
from django.core.paginator import Paginator
import json
from datetime import datetime

from src.backend.sitesearch.api.models import Site
from src.backend.sitesearch.storage.models import Document
from src.backend.sitesearch.api.views.manage import get_manager


def document_list(request, site_id):
    """
    获取站点已爬取的所有页面
    GET: 返回站点所有文档，支持分页、排序和过滤
    """
    try:
        # 验证站点是否存在
        get_object_or_404(Site, id=site_id)
        
        # 获取查询参数
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 10))
        sort_by = request.GET.get('sort_by', 'created_at')
        sort_order = request.GET.get('sort_order', 'desc')
        mimetype = request.GET.get('mimetype')
        search = request.GET.get('search', '')
        is_indexed = request.GET.get('is_indexed')
        
        # 构建查询集
        documents = Document.objects.filter(site_id=site_id)
        
        # 应用过滤器
        if mimetype:
            documents = documents.filter(mimetype=mimetype)
        
        if search:
            documents = documents.filter(title__icontains=search) | \
                        documents.filter(description__icontains=search) | \
                        documents.filter(url__icontains=search)
        
        if is_indexed is not None:
            is_indexed = is_indexed.lower() == 'true'
            documents = documents.filter(is_indexed=is_indexed)
        
        # 应用排序
        order_prefix = '-' if sort_order.lower() == 'desc' else ''
        if sort_by in ['created_at', 'updated_at', 'timestamp', 'title']:
            documents = documents.order_by(f'{order_prefix}{sort_by}')
        else:
            documents = documents.order_by('-created_at')  # 默认按创建时间降序
        
        # 分页
        paginator = Paginator(documents, page_size)
        page_obj = paginator.get_page(page)
        
        # 构建响应
        results = []
        for doc in page_obj:
            results.append({
                'id': doc.id,
                'url': doc.url,
                'title': doc.title,
                'description': doc.description,
                'mimetype': doc.mimetype,
                'content_hash': doc.content_hash,
                'created_at': doc.created_at.isoformat(),
                'updated_at': doc.updated_at.isoformat(),
                'timestamp': doc.timestamp,
                'is_indexed': doc.is_indexed,
                'version': doc.version,
                'index_operation': doc.index_operation
            })
        
        return JsonResponse({
            'results': results,
            'count': paginator.count,
            'page': page,
            'page_size': page_size,
            'total_pages': paginator.num_pages
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def document_detail(request, site_id, doc_id):
    """
    获取特定页面详情
    GET: 返回特定文档的详细信息，包括原始内容、清洗后内容和元数据
    """
    try:
        # 验证站点是否存在
        get_object_or_404(Site, id=site_id)
        
        # 获取文档详情
        doc = get_object_or_404(Document, id=doc_id, site_id=site_id)
        
        # 构建响应
        result = {
            'id': doc.id,
            'url': doc.url,
            'title': doc.title,
            'description': doc.description,
            'keywords': doc.keywords,
            'mimetype': doc.mimetype,
            'content_hash': doc.content_hash,
            'created_at': doc.created_at.isoformat(),
            'updated_at': doc.updated_at.isoformat(),
            'timestamp': doc.timestamp,
            'is_indexed': doc.is_indexed,
            'version': doc.version,
            'index_operation': doc.index_operation,
            'crawler_id': doc.crawler_id,
            'crawler_type': doc.crawler_type,
            'status_code': doc.status_code,
            'headers': doc.headers,
            'metadata': doc.metadata,
            'links': doc.links,
            'source': doc.source
        }
        
        # 添加内容（如果请求参数中包含include_content=true）
        include_content = request.GET.get('include_content', 'false').lower() == 'true'
        if include_content:
            result['content'] = doc.content
            result['clean_content'] = doc.clean_content
        
        return JsonResponse(result)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def refresh_document(request, site_id, doc_id):
    """
    手动刷新特定页面内容
    POST: 触发文档刷新任务
    """
    if request.method != 'POST':
        return JsonResponse({'error': '不支持的请求方法'}, status=405)
    
    try:
        # 验证站点是否存在
        get_object_or_404(Site, id=site_id)
        
        # 获取文档
        doc = get_object_or_404(Document, id=doc_id, site_id=site_id)
        
        # 获取管理器实例
        manager = get_manager()
        
        # 创建文档刷新任务
        task_id = manager.create_document_refresh_task(
            url=doc.url,
            site_id=site_id,
            document_id=doc_id
        )
        
        return JsonResponse({
            'success': True,
            'task_id': task_id,
            'document_id': doc_id,
            'url': doc.url,
            'site_id': site_id,
            'message': '已开始刷新文档内容'
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500) 