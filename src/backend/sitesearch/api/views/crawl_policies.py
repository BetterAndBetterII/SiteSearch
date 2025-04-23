"""
爬取策略模块视图
实现爬取策略的CRUD操作及执行功能
"""
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
import json

from src.backend.sitesearch.api.models import Site, CrawlPolicy
from src.backend.sitesearch.api.views.manage import get_manager


@csrf_exempt
def crawl_policy_list(request, site_id):
    """
    获取站点所有爬取策略或创建新爬取策略
    GET: 获取站点所有爬取策略
    POST: 创建爬取策略
    """
    # 验证站点是否存在
    site = get_object_or_404(Site, id=site_id)
    
    if request.method == 'GET':
        policies = CrawlPolicy.objects.filter(site=site)
        
        # 构建响应
        results = []
        for policy in policies:
            results.append({
                'id': policy.id,
                'name': policy.name,
                'description': policy.description,
                'start_urls': policy.start_urls,
                'url_patterns': policy.url_patterns,
                'exclude_patterns': policy.exclude_patterns,
                'max_depth': policy.max_depth,
                'max_urls': policy.max_urls,
                'crawler_type': policy.crawler_type,
                'enabled': policy.enabled,
                'created_at': policy.created_at.isoformat(),
                'updated_at': policy.updated_at.isoformat(),
                'last_executed': policy.last_executed.isoformat() if policy.last_executed else None
            })
        
        return JsonResponse({'results': results})
    
    elif request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            # 验证必填字段
            required_fields = ['name', 'start_urls']
            for field in required_fields:
                if field not in data:
                    return JsonResponse({'error': f'缺少必填字段: {field}'}, status=400)
            
            # 创建爬取策略
            policy = CrawlPolicy(
                site=site,
                name=data['name'],
                description=data.get('description', ''),
                start_urls=data['start_urls'],
                url_patterns=data.get('url_patterns', []),
                exclude_patterns=data.get('exclude_patterns', []),
                max_depth=data.get('max_depth', 3),
                max_urls=data.get('max_urls', 1000),
                crawl_delay=data.get('crawl_delay', 0.5),
                follow_robots_txt=data.get('follow_robots_txt', True),
                discover_sitemap=data.get('discover_sitemap', True),
                respect_meta_robots=data.get('respect_meta_robots', True),
                allow_subdomains=data.get('allow_subdomains', False),
                allow_external_links=data.get('allow_external_links', False),
                allowed_content_types=data.get('allowed_content_types', ['text/html']),
                crawler_type=data.get('crawler_type', 'firecrawl'),
                enabled=data.get('enabled', True),
                advanced_config=data.get('advanced_config', {})
            )
            policy.save()
            
            return JsonResponse({
                'id': policy.id,
                'name': policy.name,
                'description': policy.description,
                'site_id': site_id,
                'created_at': policy.created_at.isoformat(),
                'message': '爬取策略创建成功'
            }, status=201)
            
        except json.JSONDecodeError:
            return JsonResponse({'error': '无效的JSON数据'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': '不支持的请求方法'}, status=405)


@csrf_exempt
def crawl_policy_detail(request, site_id, policy_id):
    """
    获取、更新或删除单个爬取策略
    GET: 获取爬取策略详情
    PUT: 更新爬取策略
    DELETE: 删除爬取策略
    """
    # 验证站点是否存在
    site = get_object_or_404(Site, id=site_id)
    
    try:
        # 查找特定的爬取策略
        policy = get_object_or_404(CrawlPolicy, id=policy_id, site=site)
        
        if request.method == 'GET':
            return JsonResponse({
                'id': policy.id,
                'name': policy.name,
                'description': policy.description,
                'start_urls': policy.start_urls,
                'url_patterns': policy.url_patterns,
                'exclude_patterns': policy.exclude_patterns,
                'max_depth': policy.max_depth,
                'max_urls': policy.max_urls,
                'crawl_delay': policy.crawl_delay,
                'follow_robots_txt': policy.follow_robots_txt,
                'discover_sitemap': policy.discover_sitemap,
                'respect_meta_robots': policy.respect_meta_robots,
                'allow_subdomains': policy.allow_subdomains,
                'allow_external_links': policy.allow_external_links,
                'allowed_content_types': policy.allowed_content_types,
                'crawler_type': policy.crawler_type,
                'enabled': policy.enabled,
                'created_at': policy.created_at.isoformat(),
                'updated_at': policy.updated_at.isoformat(),
                'last_executed': policy.last_executed.isoformat() if policy.last_executed else None,
                'advanced_config': policy.advanced_config
            })
        
        elif request.method == 'PUT':
            try:
                data = json.loads(request.body)
                
                # 更新爬取策略
                if 'name' in data:
                    policy.name = data['name']
                if 'description' in data:
                    policy.description = data['description']
                if 'start_urls' in data:
                    policy.start_urls = data['start_urls']
                if 'url_patterns' in data:
                    policy.url_patterns = data['url_patterns']
                if 'exclude_patterns' in data:
                    policy.exclude_patterns = data['exclude_patterns']
                if 'max_depth' in data:
                    policy.max_depth = data['max_depth']
                if 'max_urls' in data:
                    policy.max_urls = data['max_urls']
                if 'crawl_delay' in data:
                    policy.crawl_delay = data['crawl_delay']
                if 'follow_robots_txt' in data:
                    policy.follow_robots_txt = data['follow_robots_txt']
                if 'discover_sitemap' in data:
                    policy.discover_sitemap = data['discover_sitemap']
                if 'respect_meta_robots' in data:
                    policy.respect_meta_robots = data['respect_meta_robots']
                if 'allow_subdomains' in data:
                    policy.allow_subdomains = data['allow_subdomains']
                if 'allow_external_links' in data:
                    policy.allow_external_links = data['allow_external_links']
                if 'allowed_content_types' in data:
                    policy.allowed_content_types = data['allowed_content_types']
                if 'crawler_type' in data:
                    policy.crawler_type = data['crawler_type']
                if 'enabled' in data:
                    policy.enabled = data['enabled']
                if 'advanced_config' in data:
                    policy.advanced_config = data['advanced_config']
                
                policy.save()
                
                return JsonResponse({
                    'id': policy.id,
                    'name': policy.name,
                    'description': policy.description,
                    'updated_at': policy.updated_at.isoformat(),
                    'message': '爬取策略更新成功'
                })
                
            except json.JSONDecodeError:
                return JsonResponse({'error': '无效的JSON数据'}, status=400)
        
        elif request.method == 'DELETE':
            # 获取策略名称用于响应
            policy_name = policy.name
            
            # 删除爬取策略
            policy.delete()
            
            return JsonResponse({
                'message': f'爬取策略已删除: {policy_name}',
                'id': policy_id
            })
        
        return JsonResponse({'error': '不支持的请求方法'}, status=405)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def execute_crawl_policy(request, site_id, policy_id):
    """
    立即执行特定爬取策略
    POST: 触发爬取任务
    """
    if request.method != 'POST':
        return JsonResponse({'error': '不支持的请求方法'}, status=405)
    
    try:
        # 验证站点是否存在
        site = get_object_or_404(Site, id=site_id)
        
        # 查找特定的爬取策略
        policy = get_object_or_404(CrawlPolicy, id=policy_id, site=site)
        
        # 检查策略是否启用
        if not policy.enabled:
            return JsonResponse({'error': '无法执行已禁用的爬取策略'}, status=400)
        
        # 解析请求体中的可选参数
        try:
            data = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            data = {}
        
        # 获取爬虫进程数量
        crawler_workers = data.get('crawler_workers', 1)
        
        # 获取管理器实例
        manager = get_manager()
        
        # 将爬取策略转换为任务配置
        task_config = {
            'start_urls': policy.start_urls,
            'site_id': site_id,
            'max_urls': policy.max_urls,
            'max_depth': policy.max_depth,
            'crawler_type': policy.crawler_type,
            'url_patterns': policy.url_patterns,
            'exclude_patterns': policy.exclude_patterns,
            'crawl_delay': policy.crawl_delay,
            'follow_robots_txt': policy.follow_robots_txt,
            'discover_sitemap': policy.discover_sitemap,
            'respect_meta_robots': policy.respect_meta_robots,
            'allow_subdomains': policy.allow_subdomains,
            'allow_external_links': policy.allow_external_links,
            'advanced_config': policy.advanced_config
        }
        
        # 创建爬取任务
        task_id = manager.create_crawl_task(
            start_urls=policy.start_urls,
            site_id=site_id,
            max_urls=policy.max_urls,
            max_depth=policy.max_depth,
            url_patterns=policy.url_patterns,
            exclude_patterns=policy.exclude_patterns,
            crawler_workers=crawler_workers,
            crawler_type=policy.crawler_type,
            crawler_config=policy.advanced_config
        )
        
        # 更新策略的最后执行时间
        from django.utils import timezone
        policy.last_executed = timezone.now()
        policy.save()
        
        return JsonResponse({
            'success': True,
            'task_id': task_id,
            'policy_id': policy_id,
            'site_id': site_id,
            'message': f'已开始执行爬取策略: {policy.name}'
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500) 