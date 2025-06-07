"""
站点管理模块视图
实现站点的CRUD操作
"""
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404
from asgiref.sync import sync_to_async
import json
import re

from src.backend.sitesearch.api.models import Site
from src.backend.sitesearch.storage.models import SiteDocument


def health(request):
    return JsonResponse({'status': 'ok'})

@csrf_exempt
def site_list(request):
    """
    获取所有站点列表或创建新站点
    GET: 获取所有站点列表，支持分页和过滤
    POST: 创建新站点
    """
    if request.method == 'GET':
        # 获取查询参数
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 10))
        enabled = request.GET.get('enabled')
        search = request.GET.get('search', '')
        
        # 构建查询集
        sites = Site.objects.all()
        
        # 应用过滤器
        if enabled is not None:
            enabled = enabled.lower() == 'true'
            sites = sites.filter(enabled=enabled)
        
        if search:
            sites = sites.filter(name__icontains=search) | sites.filter(description__icontains=search)
        
        # 分页
        paginator = Paginator(sites, page_size)
        page_obj = paginator.get_page(page)

        # 构建响应
        results = []
        for site in page_obj:
            results.append({
                'id': site.id,
                'name': site.name,
                'description': site.description,
                'base_url': site.base_url,
                'enabled': site.enabled,
                'icon': site.icon,
                'created_at': site.created_at.isoformat(),
                'updated_at': site.updated_at.isoformat(),
                'last_crawl_time': site.last_crawl_time.isoformat() if site.last_crawl_time else None,
                'total_documents': SiteDocument.objects.filter(site_id=site.id).count()
            })
        
        return JsonResponse({
            'results': results,
            'count': paginator.count,
            'page': page,
            'page_size': page_size,
            'total_pages': paginator.num_pages
        })
    
    elif request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            # 验证必填字段
            required_fields = ['id', 'name', 'base_url']
            for field in required_fields:
                if field not in data:
                    return JsonResponse({'error': f'缺少必填字段: {field}'}, status=400)
            
            # 检查ID是否已存在
            if Site.objects.filter(id=data['id']).exists():
                return JsonResponse({'error': f'站点ID已存在: {data["id"]}'}, status=400)
            
            # 站点ID只能包含数字、字母和下划线
            if not re.match(r'^[a-zA-Z0-9_]+$', data['id']):
                return JsonResponse({'error': '站点ID只能包含数字、字母和下划线'}, status=400)
            
            # 创建站点
            site = Site(
                id=data['id'],
                name=data['name'],
                description=data.get('description', ''),
                base_url=data['base_url'],
                icon=data.get('icon'),
                enabled=data.get('enabled', True),
                metadata=data.get('metadata', {})
            )
            site.save()
            
            return JsonResponse({
                'id': site.id,
                'name': site.name,
                'description': site.description,
                'base_url': site.base_url,
                'enabled': site.enabled,
                'created_at': site.created_at.isoformat(),
                'message': '站点创建成功'
            }, status=201)
            
        except json.JSONDecodeError:
            return JsonResponse({'error': '无效的JSON数据'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': '不支持的请求方法'}, status=405)


@csrf_exempt
async def site_detail(request, site_id):
    """
    获取、更新或删除单个站点
    GET: 获取单个站点详情
    PUT: 更新站点配置
    DELETE: 删除站点及其所有关联配置
    """
    try:
        site = await sync_to_async(get_object_or_404)(Site, id=site_id)
        
        if request.method == 'GET':
            return JsonResponse({
                'id': site.id,
                'name': site.name,
                'description': site.description,
                'base_url': site.base_url,
                'icon': site.icon,
                'enabled': site.enabled,
                'created_at': site.created_at.isoformat(),
                'updated_at': site.updated_at.isoformat(),
                'last_crawl_time': site.last_crawl_time.isoformat() if site.last_crawl_time else None,
                'total_documents': site.total_documents,
                'metadata': site.metadata
            })
        
        elif request.method == 'PUT':
            try:
                data = json.loads(request.body)
                
                # 更新站点信息
                if 'name' in data:
                    site.name = data['name']
                if 'description' in data:
                    site.description = data['description']
                if 'base_url' in data:
                    site.base_url = data['base_url']
                if 'icon' in data:
                    site.icon = data['icon']
                if 'enabled' in data:
                    site.enabled = data['enabled']
                if 'metadata' in data:
                    site.metadata = data['metadata']
                
                await site.asave()
                
                return JsonResponse({
                    'id': site.id,
                    'name': site.name,
                    'description': site.description,
                    'base_url': site.base_url,
                    'enabled': site.enabled,
                    'updated_at': site.updated_at.isoformat(),
                    'message': '站点更新成功'
                })
                
            except json.JSONDecodeError:
                return JsonResponse({'error': '无效的JSON数据'}, status=400)
        
        elif request.method == 'DELETE':
            # 获取站点名称用于响应
            site_name = site.name
            
            # 删除站点 ，删除文档站点关系，删除文档，删除index
            from src.backend.sitesearch.indexer.index_manager import IndexerFactory
            indexer = IndexerFactory.get_instance(site_id)
            await site.adelete()
            await indexer.remove_all_documents()
            
            return JsonResponse({
                'message': f'站点已删除: {site_name}',
                'id': site_id
            })
        
        return JsonResponse({'error': '不支持的请求方法'}, status=405)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def site_status(request, site_id):
    """
    获取站点当前爬取状态、队列状态、工作进程状态
    GET: 返回站点状态信息
    """
    try:
        site = get_object_or_404(Site, id=site_id)
        
        # 这里需要从MultiProcessSiteSearchManager获取站点相关状态
        # 假设manager实例可以从某个模块导入
        from src.backend.sitesearch.api.views.manage import get_manager
        manager = get_manager()
        
        # 获取站点相关的队列状态
        queues = {}
        for queue_name in ["crawler", "cleaner", "storage"]:
            queue_metrics = manager.get_queue_metrics(queue_name)
            if queue_metrics:
                queues[queue_name] = queue_metrics
        
        # 获取站点相关的工作进程状态
        workers = manager.get_workers_count()
        
        # 构建响应
        status = {
            'site_id': site_id,
            'site_name': site.name,
            'enabled': site.enabled,
            'last_crawl_time': site.last_crawl_time.isoformat() if site.last_crawl_time else None,
            'total_documents': site.total_documents,
            'queues': queues,
            'workers': workers
        }
        
        return JsonResponse(status)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def site_crawl_history(request, site_id):
    """
    获取站点爬取历史记录
    GET: 返回站点爬取历史记录，支持按时间范围过滤
    """
    try:
        # 验证站点是否存在
        get_object_or_404(Site, id=site_id)
        
        # 获取查询参数
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 10))
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        
        # 从存储模块中导入CrawlHistory模型
        from src.backend.sitesearch.storage.models import CrawlHistory
        
        # 获取与站点ID相关的爬取历史记录
        # 假设CrawlHistory的document外键关联到Document模型，Document有site_id字段
        history_records = CrawlHistory.objects.filter(document__site_id=site_id)
        
        # 应用日期过滤
        if start_date:
            history_records = history_records.filter(created_at__gte=start_date)
        if end_date:
            history_records = history_records.filter(created_at__lte=end_date)
        
        # 按时间降序排序
        history_records = history_records.order_by('-created_at')
        
        # 分页
        paginator = Paginator(history_records, page_size)
        page_obj = paginator.get_page(page)
        
        # 构建响应
        results = []
        for record in page_obj:
            results.append({
                'id': record.id,
                'url': record.url,
                'timestamp': record.timestamp,
                'version': record.version,
                'change_type': record.change_type,
                'created_at': record.created_at.isoformat(),
                'content_hash': record.content_hash,
                'metadata': record.metadata
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