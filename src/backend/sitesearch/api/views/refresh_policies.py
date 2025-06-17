"""
刷新策略模块视图
实现站点内容刷新策略的管理
"""
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
import json
import uuid
from django.utils import timezone

from src.backend.sitesearch.api.models import Site, RefreshPolicy
from src.backend.sitesearch.api.views.manage import get_manager


@csrf_exempt
def refresh_policy(request, site_id):
    """
    获取或创建/更新站点内容刷新策略
    GET: 获取站点内容刷新策略
    POST: 创建内容刷新策略
    PUT: 更新内容刷新策略
    """
    # 验证站点是否存在
    site = get_object_or_404(Site, id=site_id)
    
    if request.method == 'GET':
        # 尝试获取站点的刷新策略
        try:
            policy = RefreshPolicy.objects.get(site=site)
            
            return JsonResponse({
                'id': policy.id,
                'name': policy.name,
                'description': policy.description,
                'strategy': policy.strategy,
                'refresh_interval_days': policy.refresh_interval_days,
                'url_patterns': policy.url_patterns,
                'exclude_patterns': policy.exclude_patterns,
                'max_age_days': policy.max_age_days,
                'priority_patterns': policy.priority_patterns,
                'created_at': policy.created_at.isoformat(),
                'updated_at': policy.updated_at.isoformat(),
                'last_refresh': policy.last_refresh.isoformat() if policy.last_refresh else None,
                'next_refresh': policy.next_refresh.isoformat() if policy.next_refresh else None,
                'enabled': policy.enabled,
                'advanced_config': policy.advanced_config
            })
            
        except RefreshPolicy.DoesNotExist:
            return JsonResponse({'message': '站点尚未配置刷新策略'}, status=404)
        
    elif request.method == 'POST':
        # 检查是否已经存在刷新策略
        if RefreshPolicy.objects.filter(site=site).exists():
            return JsonResponse({'error': '站点已有刷新策略，请使用PUT方法更新'}, status=400)
        
        try:
            data = json.loads(request.body)
            
            # 创建刷新策略
            policy = RefreshPolicy(
                site=site,
                name=data.get('name', '默认刷新策略'),
                description=data.get('description', ''),
                strategy=data.get('strategy', 'incremental'),
                refresh_interval_days=data.get('refresh_interval_days', 7),
                url_patterns=data.get('url_patterns', []),
                exclude_patterns=data.get('exclude_patterns', []),
                max_age_days=data.get('max_age_days', 30),
                priority_patterns=data.get('priority_patterns', []),
                enabled=data.get('enabled', True),
                advanced_config=data.get('advanced_config', {})
            )
            
            # 计算下次刷新时间
            if policy.enabled:
                import datetime
                policy.next_refresh = timezone.now() + datetime.timedelta(days=policy.refresh_interval_days)
            
            policy.save()
            
            return JsonResponse({
                'id': policy.id,
                'name': policy.name,
                'strategy': policy.strategy,
                'created_at': policy.created_at.isoformat(),
                'next_refresh': policy.next_refresh.isoformat() if policy.next_refresh else None,
                'message': '刷新策略创建成功'
            }, status=201)
            
        except json.JSONDecodeError:
            return JsonResponse({'error': '无效的JSON数据'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    elif request.method == 'PUT':
        # 获取刷新策略或创建新的
        policy, created = RefreshPolicy.objects.get_or_create(
            site=site,
            defaults={
                'name': '默认刷新策略',
                'strategy': 'incremental',
                'refresh_interval_days': 7
            }
        )
        
        try:
            data = json.loads(request.body)
            
            # 更新刷新策略
            if 'name' in data:
                policy.name = data['name']
            if 'description' in data:
                policy.description = data['description']
            if 'strategy' in data:
                policy.strategy = data['strategy']
            if 'refresh_interval_days' in data:
                policy.refresh_interval_days = data['refresh_interval_days']
            if 'url_patterns' in data:
                policy.url_patterns = data['url_patterns']
            if 'exclude_patterns' in data:
                policy.exclude_patterns = data['exclude_patterns']
            if 'max_age_days' in data:
                policy.max_age_days = data['max_age_days']
            if 'priority_patterns' in data:
                policy.priority_patterns = data['priority_patterns']
            if 'advanced_config' in data:
                policy.advanced_config = data['advanced_config']
            
            # 如果启用状态发生变化
            if 'enabled' in data:
                policy.enabled = data['enabled']
                
                # 如果从禁用变为启用，计算下次刷新时间
                if policy.enabled and not policy.next_refresh:
                    import datetime
                    policy.next_refresh = timezone.now() + datetime.timedelta(days=policy.refresh_interval_days)
            
            policy.save()
            
            return JsonResponse({
                'id': policy.id,
                'name': policy.name,
                'strategy': policy.strategy,
                'updated_at': policy.updated_at.isoformat(),
                'next_refresh': policy.next_refresh.isoformat() if policy.next_refresh else None,
                'message': '刷新策略更新成功'
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'error': '无效的JSON数据'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': '不支持的请求方法'}, status=405)


@csrf_exempt
def execute_refresh(request, site_id):
    """
    执行站点全量内容刷新
    POST: 将一个刷新任务推送到后台队列，并立即返回。
    """
    if request.method != 'POST':
        return JsonResponse({'error': '不支持的请求方法'}, status=405)
    
    try:
        # 验证站点是否存在
        site = get_object_or_404(Site, id=site_id)
        
        # 解析请求体中的可选参数
        try:
            data = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            data = {}
        
        # 获取刷新策略参数
        strategy = data.get('strategy')
        url_patterns = data.get('url_patterns', [])
        exclude_patterns = data.get('exclude_patterns', [])
        max_age_days = data.get('max_age_days')
        priority_patterns = data.get('priority_patterns', [])
        
        # 如果未指定策略，尝试使用站点的默认刷新策略
        if not strategy:
            try:
                policy = RefreshPolicy.objects.get(site=site)
                strategy = policy.strategy
                if not url_patterns:
                    url_patterns = policy.url_patterns
                if not exclude_patterns:
                    exclude_patterns = policy.exclude_patterns
                if not max_age_days:
                    max_age_days = policy.max_age_days
                if not priority_patterns:
                    priority_patterns = policy.priority_patterns
            except RefreshPolicy.DoesNotExist:
                strategy = 'incremental'  # 默认使用增量刷新策略

        # 获取 pipeline manager
        manager = get_manager()

        # 创建一个爬取更新任务，这将设置爬虫和队列
        crawl_task_id = manager.create_crawl_update_task(
            site_id=site.id,
            urls=[],  # 初始URL列表为空
            crawler_type="httpx",
            crawler_workers=6
        )
        
        # 定义任务数据
        task_data = {
            'task_type': 'site_refresh',
            'task_id': f"refresh-{site_id}-{uuid.uuid4().hex[:8]}",
            'site_id': site_id,
            'crawl_task_id': crawl_task_id,  # 传递爬取任务ID
            'strategy': strategy,
            'url_patterns': url_patterns,
            'exclude_patterns': exclude_patterns,
            'max_age_days': max_age_days,
            'priority_patterns': priority_patterns
        }
        
        # 将任务推送到专门的刷新队列
        refresh_queue_name = "sitesearch:queue:refresh"
        manager.redis_client.lpush(refresh_queue_name, json.dumps(task_data))

        return JsonResponse({
            'success': True,
            'site_id': site_id,
            'message': f'已成功将站点内容刷新任务派发到后台队列',
            'crawl_task_id': crawl_task_id
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500) 