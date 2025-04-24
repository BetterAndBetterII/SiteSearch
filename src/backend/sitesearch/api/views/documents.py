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
from src.backend.sitesearch.storage.models import Document, SiteDocument
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
        
        # 构建查询集 - 使用新的多站点关系查询
        # 先获取站点关联的所有文档ID
        site_documents = SiteDocument.objects.filter(site_id=site_id)
        document_ids = site_documents.values_list('document_id', flat=True)
        documents = Document.objects.filter(id__in=document_ids)
        
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
                'index_operation': doc.index_operation,
                'site_ids': doc.get_site_ids()  # 添加所有关联的站点ID
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
        
        # 获取文档详情 - 确保文档与站点相关联
        doc = get_object_or_404(Document, id=doc_id)
        
        # 验证文档是否属于指定站点
        if not SiteDocument.objects.filter(document_id=doc_id, site_id=site_id).exists():
            return JsonResponse({'error': '文档不属于指定站点'}, status=404)
        
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
            'source': doc.source,
            'site_ids': doc.get_site_ids(),  # 添加所有关联的站点ID
            'clean_content': doc.clean_content
        }
        
        # 添加内容（如果请求参数中包含include_content=true）
        include_content = request.GET.get('include_content', 'false').lower() == 'true'
        if include_content:
            result['content'] = doc.content
            result['clean_content'] = doc.clean_content
        
        return JsonResponse(result)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def document_search(request, site_id):
    """
    搜索特定站点文档
    GET: 返回特定站点所有文档，支持分页、排序和过滤
    """
    try:
        # 验证站点是否存在
        get_object_or_404(Site, id=site_id)
        
        # 获取查询参数
        query = request.GET.get('query', '')
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 10))
        
        if not query:
            return JsonResponse({
                'error': '缺少查询关键词',
                'message': '请提供query参数'
            }, status=400)
        
        # 获取管理器实例
        manager = get_manager()
        
        # 从存储模块搜索文档 - 使用新的带有site_id参数的搜索函数
        from src.backend.sitesearch.storage.utils import search_documents
        search_results = search_documents(query, site_id, limit=1000)
        
        # 分页
        paginator = Paginator(search_results, page_size)
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
                'score': 0.0,  # 简单搜索没有相关性得分
                'highlights': {
                    'title': doc.title,
                    'description': doc.description,
                    'content': ''  # 简单搜索没有高亮片段
                },
                'site_ids': doc.get_site_ids()  # 添加所有关联的站点ID
            })
        
        return JsonResponse({
            'results': results,
            'count': paginator.count,
            'page': page,
            'page_size': page_size,
            'total_pages': paginator.num_pages,
            'query': query
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
def document_delete(request, site_id):
    """
    删除特定站点所有文档
    POST: 删除特定站点所有文档
    """
    if request.method != 'POST':
        return JsonResponse({'error': '不支持的请求方法'}, status=405)
    
    try:
        # 验证站点是否存在
        site = get_object_or_404(Site, id=site_id)
        
        # 解析请求数据
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            data = {}
        
        # 支持批量删除特定文档
        document_ids = data.get('document_ids', [])
        delete_all = data.get('delete_all', False)
        
        if not document_ids and not delete_all:
            return JsonResponse({
                'error': '缺少必要参数',
                'message': '请提供document_ids参数或设置delete_all=true'
            }, status=400)
        
        # 获取存储模块的删除函数
        from src.backend.sitesearch.storage.manager import DataStorage
        storage = DataStorage()
        
        deleted_count = 0
        failed_count = 0
        
        if delete_all:
            # 获取站点的所有文档ID
            site_documents = SiteDocument.objects.filter(site_id=site_id)
            document_ids = site_documents.values_list('document_id', flat=True)
            documents = Document.objects.filter(id__in=document_ids)
            total_count = documents.count()
            
            for doc in documents:
                # 使用新的支持站点的删除方法
                result = storage.delete_document(doc.url, site_id)
                if result:
                    deleted_count += 1
                else:
                    failed_count += 1
            
            return JsonResponse({
                'success': True,
                'site_id': site_id,
                'deleted_count': deleted_count,
                'failed_count': failed_count,
                'total_count': total_count,
                'message': f'已删除站点 {site_id} 的 {deleted_count}/{total_count} 个文档'
            })
        else:
            # 删除指定的文档
            results = []
            for doc_id in document_ids:
                try:
                    # 验证文档是否属于指定站点
                    site_doc = SiteDocument.objects.filter(document_id=doc_id, site_id=site_id).first()
                    if not site_doc:
                        failed_count += 1
                        results.append({
                            'id': doc_id,
                            'success': False,
                            'error': '文档不属于该站点'
                        })
                        continue
                    
                    doc = Document.objects.get(id=doc_id)
                    # 使用新的支持站点的删除方法
                    result = storage.delete_document(doc.url, site_id)
                    
                    if result:
                        deleted_count += 1
                        results.append({
                            'id': doc_id,
                            'success': True
                        })
                    else:
                        failed_count += 1
                        results.append({
                            'id': doc_id,
                            'success': False,
                            'error': '删除失败'
                        })
                except Document.DoesNotExist:
                    failed_count += 1
                    results.append({
                        'id': doc_id,
                        'success': False,
                        'error': '文档不存在'
                    })
            
            return JsonResponse({
                'success': True,
                'site_id': site_id,
                'deleted_count': deleted_count,
                'failed_count': failed_count,
                'total_count': len(document_ids),
                'results': results,
                'message': f'已删除 {deleted_count}/{len(document_ids)} 个文档'
            })
        
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
        doc = get_object_or_404(Document, id=doc_id)
        
        # 验证文档是否属于指定站点
        if not SiteDocument.objects.filter(document_id=doc_id, site_id=site_id).exists():
            return JsonResponse({'error': '文档不属于指定站点'}, status=404)
        
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