"""
定时任务模块视图
实现爬取策略的定时执行计划管理
"""
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
import json
from django.utils import timezone
import datetime

from src.backend.sitesearch.api.models import Site, CrawlPolicy, ScheduleTask, RefreshPolicy
from src.backend.sitesearch.api.views.manage import get_manager


@csrf_exempt
def check_policy_execution(request):
    """
    检查所有站点的爬取策略和刷新策略是否需要执行
    GET: 检查并返回需要执行的策略列表
    POST: 检查并执行需要执行的策略
    """
    # 获取当前时间
    current_time = timezone.now()
    
    # 初始化结果列表
    results = []
    
    # 获取所有站点
    sites = Site.objects.all()
    
    for site in sites:
        site_result = {
            'site_id': site.id,
            'site_name': site.name,
            'crawl_policies': [],
            'refresh_policy': None
        }
        
        # 检查爬取策略
        crawl_policies = CrawlPolicy.objects.filter(site=site, enabled=True)
        for policy in crawl_policies:
            should_execute = False
            reason = ""
            
            # 如果策略从未执行过，应该执行
            if not policy.last_executed:
                should_execute = True
                reason = "策略从未执行过"
            else:
                # 检查是否有相关联的定时任务
                schedules = ScheduleTask.objects.filter(crawl_policy=policy, enabled=True)
                
                for schedule in schedules:
                    if schedule.schedule_type == 'once' and schedule.one_time_date and schedule.one_time_date <= current_time and not schedule.last_run:
                        should_execute = True
                        reason = "单次执行时间已到"
                        break
                        
                    elif schedule.schedule_type == 'interval' and schedule.interval_seconds:
                        # 计算上次执行后的间隔时间
                        last_run = schedule.last_run or policy.last_executed
                        if last_run:
                            time_diff = current_time - last_run
                            if time_diff.total_seconds() >= schedule.interval_seconds:
                                should_execute = True
                                reason = f"间隔执行时间已到 (间隔{schedule.interval_seconds}秒)"
                                break
                        else:
                            should_execute = True
                            reason = "间隔执行且从未执行过"
                            break
                            
                    # Cron表达式的计算复杂，这里简化处理为检查next_run字段
                    elif schedule.schedule_type == 'cron' and schedule.next_run and schedule.next_run <= current_time:
                        should_execute = True
                        reason = "Cron表达式执行时间已到"
                        break
            
            if should_execute:
                site_result['crawl_policies'].append({
                    'id': policy.id,
                    'name': policy.name,
                    'reason': reason,
                    'policy_type': 'crawl'
                })
        
        # 检查刷新策略
        try:
            refresh_policy = RefreshPolicy.objects.get(site=site, enabled=True)
            
            # 检查刷新策略是否需要执行
            should_execute = False
            reason = ""
            
            # 如果策略从未执行过，应该执行
            if not refresh_policy.last_refresh:
                should_execute = True
                reason = "刷新策略从未执行过"
            elif refresh_policy.next_refresh and refresh_policy.next_refresh <= current_time:
                # 如果下次刷新时间已到
                should_execute = True
                reason = "刷新间隔时间已到"
            
            if should_execute:
                site_result['refresh_policy'] = {
                    'id': refresh_policy.id,
                    'name': refresh_policy.name,
                    'reason': reason,
                    'policy_type': 'refresh'
                }
        except RefreshPolicy.DoesNotExist:
            pass
        
        # 如果站点有需要执行的策略，添加到结果列表
        if site_result['crawl_policies'] or site_result['refresh_policy']:
            results.append(site_result)
    
    # 获取管理器实例
    manager = get_manager()
    executed_tasks = []
    
    # 遍历每个站点执行需要的策略
    for site_result in results:
        site_id = site_result['site_id']
        
        # 执行需要执行的爬取策略
        for policy_info in site_result['crawl_policies']:
            policy_id = policy_info['id']
            policy = CrawlPolicy.objects.get(id=policy_id)
            
            try:
                # 创建爬取任务
                task_ids = []
                crawler_workers = 1  # 默认工作进程数
                
                for start_url in policy.start_urls:
                    task_id = manager.create_crawl_task(
                        start_url=start_url,
                        site_id=site_id,
                        max_urls=policy.max_urls,
                        max_depth=policy.max_depth,
                        regpattern=policy.url_patterns[0] if policy.url_patterns else '*',
                        crawler_workers=crawler_workers,
                        crawler_type=policy.crawler_type,
                    )
                    task_ids.append(task_id)
                
                # 更新策略的最后执行时间
                policy.last_executed = current_time
                policy.save()
                
                # 更新相关定时任务的最后执行时间和下次执行时间
                schedules = ScheduleTask.objects.filter(crawl_policy=policy, enabled=True)
                for schedule in schedules:
                    schedule.last_run = current_time
                    
                    # 计算下次运行时间
                    if schedule.schedule_type == 'interval' and schedule.interval_seconds:
                        schedule.next_run = current_time + datetime.timedelta(seconds=schedule.interval_seconds)
                    # Cron表达式的下次运行时间计算略过
                    
                    schedule.run_count = (schedule.run_count or 0) + 1
                    schedule.save()
                
                executed_tasks.append({
                    'site_id': site_id,
                    'site_name': site_result['site_name'],
                    'policy_id': policy_id,
                    'policy_type': 'crawl',
                    'policy_name': policy.name,
                    'task_ids': task_ids,
                    'executed_at': current_time.isoformat()
                })
            except Exception as e:
                executed_tasks.append({
                    'site_id': site_id,
                    'site_name': site_result['site_name'],
                    'policy_id': policy_id,
                    'policy_type': 'crawl',
                    'policy_name': policy.name,
                    'error': str(e)
                })
        
        # 执行需要执行的刷新策略
        if site_result['refresh_policy']:
            try:
                refresh_policy = RefreshPolicy.objects.get(id=site_result['refresh_policy']['id'])
                
                # 获取存储管理器
                from src.backend.sitesearch.storage.utils import get_documents_by_site
                documents = get_documents_by_site(site_id, limit=99999999)
                urls = [doc.url for doc in documents]
                
                # 创建刷新任务
                task_id = manager.create_crawl_update_task(
                    site_id=site_id,
                    urls=urls,
                    crawler_type="httpx",
                    crawler_workers=1
                )
                
                # 更新刷新策略的最后刷新时间和下次刷新时间
                refresh_policy.last_refresh = current_time
                if refresh_policy.enabled and refresh_policy.refresh_interval_days:
                    refresh_policy.next_refresh = current_time + datetime.timedelta(days=refresh_policy.refresh_interval_days)
                refresh_policy.save()
                
                executed_tasks.append({
                    'site_id': site_id,
                    'site_name': site_result['site_name'],
                    'policy_id': refresh_policy.id,
                    'policy_type': 'refresh',
                    'policy_name': refresh_policy.name,
                    'task_id': task_id,
                    'executed_at': current_time.isoformat()
                })
            except Exception as e:
                executed_tasks.append({
                    'site_id': site_id,
                    'site_name': site_result['site_name'],
                    'policy_id': site_result['refresh_policy']['id'],
                    'policy_type': 'refresh',
                    'policy_name': site_result['refresh_policy']['name'],
                    'error': str(e)
                })
        
    return JsonResponse({
        'success': True,
        'executed_tasks': executed_tasks,
        'execution_time': current_time.isoformat()
    })


@csrf_exempt
def create_schedule(request, site_id, policy_id):
    """
    为爬取策略设置定时执行计划
    POST: 创建定时任务
    """
    if request.method != 'POST':
        return JsonResponse({'error': '不支持的请求方法'}, status=405)
    
    try:
        # 验证站点和爬取策略是否存在
        site = get_object_or_404(Site, id=site_id)
        policy = get_object_or_404(CrawlPolicy, id=policy_id, site=site)
        
        # 解析请求体
        data = json.loads(request.body)
        
        # 验证必填字段
        required_fields = ['name', 'schedule_type']
        for field in required_fields:
            if field not in data:
                return JsonResponse({'error': f'缺少必填字段: {field}'}, status=400)
        
        # 获取调度类型
        schedule_type = data['schedule_type']
        
        # 验证调度类型
        valid_schedule_types = ['once', 'interval', 'cron']
        if schedule_type not in valid_schedule_types:
            return JsonResponse({'error': f'无效的调度类型: {schedule_type}'}, status=400)
        
        # 根据调度类型验证必需的字段
        if schedule_type == 'once' and not data.get('one_time_date'):
            return JsonResponse({'error': '单次执行需要提供执行时间'}, status=400)
        elif schedule_type == 'interval' and not data.get('interval_seconds'):
            return JsonResponse({'error': '间隔执行需要提供间隔时间'}, status=400)
        elif schedule_type == 'cron' and not data.get('cron_expression'):
            return JsonResponse({'error': 'Cron表达式执行需要提供Cron表达式'}, status=400)
        
        # 创建定时任务
        schedule = ScheduleTask(
            crawl_policy=policy,
            name=data['name'],
            description=data.get('description', ''),
            schedule_type=schedule_type,
            cron_expression=data.get('cron_expression'),
            interval_seconds=data.get('interval_seconds'),
            one_time_date=data.get('one_time_date'),
            start_date=data.get('start_date'),
            end_date=data.get('end_date'),
            enabled=data.get('enabled', True),
            max_runs=data.get('max_runs'),
            metadata=data.get('metadata', {})
        )
        
        # 计算下次运行时间
        # 这里需要根据不同的调度类型计算，简化处理
        if schedule_type == 'once':
            schedule.next_run = schedule.one_time_date
        elif schedule_type == 'interval' and schedule.start_date:
            schedule.next_run = max(schedule.start_date, timezone.now())
        elif schedule_type == 'interval' and schedule.interval_seconds:
            # 如果没有设置start_date，则从当前时间开始计算
            schedule.next_run = timezone.now() + datetime.timedelta(seconds=schedule.interval_seconds)
        # Cron表达式的下次运行时间需要使用croniter库计算，这里略过
        
        schedule.save()
        
        return JsonResponse({
            'id': schedule.id,
            'name': schedule.name,
            'schedule_type': schedule.schedule_type,
            'next_run': schedule.next_run.isoformat() if schedule.next_run else None,
            'policy_id': policy_id,
            'site_id': site_id,
            'message': '定时任务创建成功'
        }, status=201)
        
    except json.JSONDecodeError:
        return JsonResponse({'error': '无效的JSON数据'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def schedule_list(request, site_id):
    """
    获取站点所有定时任务
    GET: 返回站点所有定时任务
    """
    try:
        # 验证站点是否存在
        site = get_object_or_404(Site, id=site_id)
        
        # 查询站点下所有爬取策略的定时任务
        schedules = ScheduleTask.objects.filter(crawl_policy__site=site)
        
        # 构建响应
        results = []
        for schedule in schedules:
            results.append({
                'id': schedule.id,
                'name': schedule.name,
                'description': schedule.description,
                'schedule_type': schedule.schedule_type,
                'cron_expression': schedule.cron_expression,
                'interval_seconds': schedule.interval_seconds,
                'one_time_date': schedule.one_time_date.isoformat() if schedule.one_time_date else None,
                'start_date': schedule.start_date.isoformat() if schedule.start_date else None,
                'end_date': schedule.end_date.isoformat() if schedule.end_date else None,
                'created_at': schedule.created_at.isoformat(),
                'updated_at': schedule.updated_at.isoformat(),
                'last_run': schedule.last_run.isoformat() if schedule.last_run else None,
                'next_run': schedule.next_run.isoformat() if schedule.next_run else None,
                'enabled': schedule.enabled,
                'run_count': schedule.run_count,
                'max_runs': schedule.max_runs,
                'policy_id': schedule.crawl_policy.id,
                'policy_name': schedule.crawl_policy.name
            })
        
        return JsonResponse({'results': results})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def schedule_detail(request, site_id, schedule_id):
    """
    获取或更新定时任务
    GET: 获取定时任务详情
    PUT: 更新定时任务配置
    DELETE: 删除定时任务
    """
    try:
        # 验证站点是否存在
        site = get_object_or_404(Site, id=site_id)
        
        # 查找特定的定时任务
        schedule = get_object_or_404(ScheduleTask, id=schedule_id, crawl_policy__site=site)
        
        if request.method == 'GET':
            return JsonResponse({
                'id': schedule.id,
                'name': schedule.name,
                'description': schedule.description,
                'schedule_type': schedule.schedule_type,
                'cron_expression': schedule.cron_expression,
                'interval_seconds': schedule.interval_seconds,
                'one_time_date': schedule.one_time_date.isoformat() if schedule.one_time_date else None,
                'start_date': schedule.start_date.isoformat() if schedule.start_date else None,
                'end_date': schedule.end_date.isoformat() if schedule.end_date else None,
                'created_at': schedule.created_at.isoformat(),
                'updated_at': schedule.updated_at.isoformat(),
                'last_run': schedule.last_run.isoformat() if schedule.last_run else None,
                'next_run': schedule.next_run.isoformat() if schedule.next_run else None,
                'enabled': schedule.enabled,
                'job_id': schedule.job_id,
                'run_count': schedule.run_count,
                'max_runs': schedule.max_runs,
                'metadata': schedule.metadata,
                'policy_id': schedule.crawl_policy.id,
                'policy_name': schedule.crawl_policy.name,
                'site_id': site_id
            })
        
        elif request.method == 'PUT':
            try:
                data = json.loads(request.body)
                
                # 如果更改了调度类型，可能需要重新设置一些字段
                if 'schedule_type' in data:
                    schedule_type = data['schedule_type']
                    
                    # 验证调度类型
                    valid_schedule_types = ['once', 'interval', 'cron']
                    if schedule_type not in valid_schedule_types:
                        return JsonResponse({'error': f'无效的调度类型: {schedule_type}'}, status=400)
                    
                    # 根据调度类型验证必需的字段
                    if schedule_type == 'once' and not (data.get('one_time_date') or schedule.one_time_date):
                        return JsonResponse({'error': '单次执行需要提供执行时间'}, status=400)
                    elif schedule_type == 'interval' and not (data.get('interval_seconds') or schedule.interval_seconds):
                        return JsonResponse({'error': '间隔执行需要提供间隔时间'}, status=400)
                    elif schedule_type == 'cron' and not (data.get('cron_expression') or schedule.cron_expression):
                        return JsonResponse({'error': 'Cron表达式执行需要提供Cron表达式'}, status=400)
                    
                    schedule.schedule_type = schedule_type
                
                # 更新定时任务
                if 'name' in data:
                    schedule.name = data['name']
                if 'description' in data:
                    schedule.description = data['description']
                if 'cron_expression' in data:
                    schedule.cron_expression = data['cron_expression']
                if 'interval_seconds' in data:
                    schedule.interval_seconds = data['interval_seconds']
                if 'one_time_date' in data:
                    schedule.one_time_date = data['one_time_date']
                if 'start_date' in data:
                    schedule.start_date = data['start_date']
                if 'end_date' in data:
                    schedule.end_date = data['end_date']
                if 'max_runs' in data:
                    schedule.max_runs = data['max_runs']
                if 'metadata' in data:
                    schedule.metadata = data['metadata']
                
                # 如果启用状态发生变化
                if 'enabled' in data:
                    schedule.enabled = data['enabled']
                
                # 重新计算下次运行时间
                if 'schedule_type' in data or 'cron_expression' in data or 'interval_seconds' in data or 'one_time_date' in data or 'start_date' in data:
                    # 这里需要根据不同的调度类型计算，简化处理
                    if schedule.schedule_type == 'once':
                        schedule.next_run = schedule.one_time_date
                    elif schedule.schedule_type == 'interval':
                        # 如果已经运行过，下次运行时间为上次运行时间加上间隔
                        if schedule.last_run and schedule.interval_seconds:
                            schedule.next_run = schedule.last_run + datetime.timedelta(seconds=schedule.interval_seconds)
                        # 如果有开始时间，下次运行时间为开始时间或当前时间的较大值
                        elif schedule.start_date and schedule.interval_seconds:
                            schedule.next_run = max(schedule.start_date, timezone.now())
                        # 如果没有开始时间，从当前时间开始计算
                        elif schedule.interval_seconds:
                            schedule.next_run = timezone.now() + datetime.timedelta(seconds=schedule.interval_seconds)
                    # Cron表达式的下次运行时间需要使用croniter库计算，这里略过
                
                schedule.save()
                
                return JsonResponse({
                    'id': schedule.id,
                    'name': schedule.name,
                    'updated_at': schedule.updated_at.isoformat(),
                    'next_run': schedule.next_run.isoformat() if schedule.next_run else None,
                    'enabled': schedule.enabled,
                    'message': '定时任务更新成功'
                })
                
            except json.JSONDecodeError:
                return JsonResponse({'error': '无效的JSON数据'}, status=400)
        
        elif request.method == 'DELETE':
            # 获取任务名称用于响应
            schedule_name = schedule.name
            
            # 删除定时任务
            schedule.delete()
            
            return JsonResponse({
                'message': f'定时任务已删除: {schedule_name}',
                'id': schedule_id
            })
        
        return JsonResponse({'error': '不支持的请求方法'}, status=405)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def toggle_schedule(request, site_id, schedule_id):
    """
    启用/禁用定时任务
    POST: 切换定时任务状态
    """
    if request.method != 'POST':
        return JsonResponse({'error': '不支持的请求方法'}, status=405)
    
    try:
        # 验证站点是否存在
        site = get_object_or_404(Site, id=site_id)
        
        # 查找特定的定时任务
        schedule = get_object_or_404(ScheduleTask, id=schedule_id, crawl_policy__site=site)
        
        # 切换状态
        if schedule.enabled:
            # 如果当前是启用状态，则禁用
            schedule.enabled = False
            message = '定时任务已禁用'
        else:
            # 如果当前是禁用状态，则启用
            schedule.enabled = True
            message = '定时任务已启用'
            
            # 根据调度类型计算下次执行时间（如果未设置）
            if not schedule.next_run:
                if schedule.schedule_type == 'once':
                    schedule.next_run = schedule.one_time_date
                elif schedule.schedule_type == 'interval':
                    if schedule.last_run and schedule.interval_seconds:
                        schedule.next_run = schedule.last_run + datetime.timedelta(seconds=schedule.interval_seconds)
                    elif schedule.start_date and schedule.interval_seconds:
                        schedule.next_run = max(schedule.start_date, timezone.now())
                    elif schedule.interval_seconds:
                        schedule.next_run = timezone.now() + datetime.timedelta(seconds=schedule.interval_seconds)
                # Cron表达式的下次运行时间需要使用croniter库计算，这里略过
        
        schedule.save()
        
        return JsonResponse({
            'id': schedule.id,
            'name': schedule.name,
            'enabled': schedule.enabled,
            'next_run': schedule.next_run.isoformat() if schedule.next_run else None,
            'message': message
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500) 