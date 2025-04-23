"""
定时任务模块视图
实现爬取策略的定时执行计划管理
"""
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
import json
from django.utils import timezone

from src.backend.sitesearch.api.models import Site, CrawlPolicy, ScheduleTask
from src.backend.sitesearch.api.views.manage import get_manager


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
        # Cron表达式的下次运行时间需要使用croniter库计算，这里略过
        
        schedule.save()
        
        # 如果启用了，注册到调度器
        if schedule.enabled:
            # 获取管理器实例
            manager = get_manager()
            
            # 注册定时任务
            job_id = manager.register_schedule_task(schedule.id)
            
            # 更新任务的job_id
            schedule.job_id = job_id
            schedule.save(update_fields=['job_id'])
        
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
                
                # 获取管理器实例
                manager = get_manager()
                
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
                if 'enabled' in data and data['enabled'] != schedule.enabled:
                    # 如果从禁用变为启用
                    if data['enabled'] and not schedule.enabled:
                        # 注册到调度器
                        job_id = manager.register_schedule_task(schedule.id)
                        schedule.job_id = job_id
                    # 如果从启用变为禁用
                    elif not data['enabled'] and schedule.enabled and schedule.job_id:
                        # 从调度器移除
                        manager.unregister_schedule_task(schedule.job_id)
                        schedule.job_id = None
                    
                    schedule.enabled = data['enabled']
                
                # 重新计算下次运行时间
                if 'schedule_type' in data or 'cron_expression' in data or 'interval_seconds' in data or 'one_time_date' in data or 'start_date' in data:
                    # 这里需要根据不同的调度类型计算，简化处理
                    if schedule.schedule_type == 'once':
                        schedule.next_run = schedule.one_time_date
                    elif schedule.schedule_type == 'interval' and schedule.start_date:
                        # 如果已经运行过，下次运行时间为上次运行时间加上间隔
                        if schedule.last_run:
                            import datetime
                            schedule.next_run = schedule.last_run + datetime.timedelta(seconds=schedule.interval_seconds)
                        else:
                            schedule.next_run = max(schedule.start_date, timezone.now())
                    # Cron表达式的下次运行时间需要使用croniter库计算，这里略过
                
                schedule.save()
                
                # 如果任务已启用并且调度设置发生变化，需要更新调度器
                if schedule.enabled and schedule.job_id and ('schedule_type' in data or 'cron_expression' in data or 'interval_seconds' in data or 'one_time_date' in data):
                    # 重新注册到调度器
                    manager.unregister_schedule_task(schedule.job_id)
                    job_id = manager.register_schedule_task(schedule.id)
                    schedule.job_id = job_id
                    schedule.save(update_fields=['job_id'])
                
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
            # 获取管理器实例
            manager = get_manager()
            
            # 如果任务已启用，从调度器移除
            if schedule.enabled and schedule.job_id:
                manager.unregister_schedule_task(schedule.job_id)
            
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
        
        # 获取管理器实例
        manager = get_manager()
        
        # 切换状态
        if schedule.enabled:
            # 如果当前是启用状态，则禁用
            if schedule.job_id:
                manager.unregister_schedule_task(schedule.job_id)
                schedule.job_id = None
            
            schedule.enabled = False
            message = '定时任务已禁用'
        else:
            # 如果当前是禁用状态，则启用
            job_id = manager.register_schedule_task(schedule.id)
            schedule.job_id = job_id
            schedule.enabled = True
            message = '定时任务已启用'
        
        schedule.save()
        
        return JsonResponse({
            'id': schedule.id,
            'name': schedule.name,
            'enabled': schedule.enabled,
            'message': message
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500) 