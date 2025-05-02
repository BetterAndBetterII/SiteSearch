# 在Django views.py中实现管理接口
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
import os

from src.backend.sitesearch.pipeline_manager import component_worker, MultiProcessSiteSearchManager
# 全局管理器实例
_manager = None

def get_manager():
    global _manager
    if _manager is None:
        redis_url = os.getenv('REDIS_URL')
        milvus_uri = os.getenv('MILVUS_URI')
        _manager = MultiProcessSiteSearchManager(redis_url, milvus_uri)
        _manager.initialize_components()
        # 启动共享组件
        _manager.start_shared_components(
            cleaner_workers=1,
            storage_workers=1,
            indexer_workers=1
        )
        
        # 启动监控
        _manager.start_monitoring()
    return _manager

@csrf_exempt
def manage_components(request):
    """管理组件API"""
    if request.method == 'POST':
        data = json.loads(request.body)
        action = data.get('action')
        component = data.get('component')
        
        manager = get_manager()
        
        if action == 'start':
            success = manager.start_component(component)
        elif action == 'stop':
            success = manager.stop_component(component)
        elif action == 'restart':
            manager.stop_component(component)
            success = manager.start_component(component)
        else:
            return JsonResponse({'error': '未知操作'}, status=400)
            
        return JsonResponse({'success': success})
    
    return JsonResponse({'error': '不支持的请求方法'}, status=405)

@csrf_exempt
def scale_workers(request):
    """扩缩工作进程API"""
    if request.method == 'POST':
        data = json.loads(request.body)
        component_type = data.get('component_type')
        worker_count = data.get('worker_count', 1)
        
        # 使用 adjust_workers 方法动态调整工作进程数量
        manager = get_manager()
        result = manager.adjust_workers(component_type, worker_count)
            
        return JsonResponse({'success': result})
    
    return JsonResponse({'error': '不支持的请求方法'}, status=405)

def get_system_status(request):
    """获取系统状态API"""
    manager = get_manager()
    status = manager.get_system_status()
    return JsonResponse(status)

def get_workers_count(request):
    """获取工作进程数量API"""
    manager = get_manager()
    workers_count = manager.get_workers_count()
    return JsonResponse({'workers_count': workers_count})

def get_queue_metrics(request, queue_name=None):
    """获取队列指标API"""
    manager = get_manager()
    
    if queue_name:
        # 获取特定队列的指标
        metrics = manager.get_queue_metrics(queue_name)
        return JsonResponse({queue_name: metrics})
    else:
        # 获取所有队列的指标
        metrics = {}
        for queue_name in ["crawler", "cleaner", "storage", "indexer"]:
            metrics[queue_name] = manager.get_queue_metrics(queue_name)
        
        # 添加任务队列的指标
        for task_id, task_info in manager.tasks.items():
            input_queue = task_info.get("input_queue")
            if input_queue:
                task_queue_name = f"task_{task_id}"
                metrics[task_queue_name] = manager.get_queue_metrics(input_queue)
                
        return JsonResponse({'queues': metrics})

def get_component_status(request, component_type=None):
    """获取组件状态API"""
    manager = get_manager()
    
    if component_type:
        # 获取特定组件的状态
        if component_type in ["cleaner", "storage", "indexer", "crawler"]:
            status = manager.get_component_status(component_type)
            return JsonResponse({component_type: status})
        else:
            return JsonResponse({'error': '无效的组件类型'}, status=400)
    else:
        # 获取所有组件的状态
        components = {}
        for component_type in ["crawler", "cleaner", "storage", "indexer"]:
            components[component_type] = manager.get_component_status(component_type)
        return JsonResponse({'components': components})

@csrf_exempt
def create_task(request):
    """创建爬取任务API"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            start_url = data.get('start_url')
            site_id = data.get('site_id')
            max_urls = data.get('max_urls')
            max_depth = data.get('max_depth')
            regpattern = data.get('regpattern', '*')
            crawler_workers = data.get('crawler_workers', 4)
            crawler_type = data.get('crawler_type', 'httpx')
            
            if not start_url:
                return JsonResponse({'error': '缺少起始URL'}, status=400)
                
            manager = get_manager()
            task_id = manager.create_crawl_task(
                start_url=start_url,
                site_id=site_id,
                max_urls=max_urls,
                max_depth=max_depth,
                regpattern=regpattern,
                crawler_type=crawler_type,
                crawler_workers=crawler_workers
            )
            
            return JsonResponse({
                'success': True,
                'task_id': task_id,
                'message': f'已创建任务 {task_id}',
                'task_config': {
                    'start_url': start_url,
                    'site_id': site_id,
                    'max_urls': max_urls,
                    'max_depth': max_depth,
                    'regpattern': regpattern
                }
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': '不支持的请求方法'}, status=405)

@csrf_exempt
def manage_task(request, task_id):
    """管理任务API"""
    manager = get_manager()
    
    if request.method == 'GET':
        # 获取任务状态
        task_status = manager.get_task_status(task_id)
        if 'error' in task_status:
            return JsonResponse(task_status, status=404)
        return JsonResponse(task_status)
    
    elif request.method == 'POST':
        # 操作任务
        try:
            data = json.loads(request.body)
            action = data.get('action')
            
            if action == 'stop':
                success = manager.stop_task(task_id)
                return JsonResponse({
                    'success': success,
                    'message': f'已停止任务 {task_id}' if success else f'停止任务 {task_id} 失败'
                })
            elif action == 'add_url':
                url = data.get('url')
                site_id = data.get('site_id')
                if not url:
                    return JsonResponse({'error': '缺少URL'}, status=400)
                success = manager.add_url_to_task_queue(task_id, url, site_id)
                return JsonResponse({
                    'success': success,
                    'message': f'已添加URL到任务 {task_id}' if success else f'添加URL到任务 {task_id} 失败'
                })
            else:
                return JsonResponse({'error': '未知操作'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    elif request.method == 'DELETE':
        # 删除任务（停止并清理相关资源）
        success = manager.stop_task(task_id)
        return JsonResponse({
            'success': success,
            'message': f'已删除任务 {task_id}' if success else f'删除任务 {task_id} 失败'
        })
    
    return JsonResponse({'error': '不支持的请求方法'}, status=405)

def get_all_tasks(request):
    """获取所有任务API"""
    manager = get_manager()
    tasks = manager.get_all_tasks_status()
    return JsonResponse({'tasks': tasks})

@csrf_exempt
def toggle_monitoring(request):
    """切换系统监控API"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            action = data.get('action')
            
            manager = get_manager()
            
            if action == 'start':
                manager.start_monitoring()
                return JsonResponse({
                    'success': True,
                    'message': '已启动系统监控'
                })
            elif action == 'stop':
                manager.stop_monitoring()
                return JsonResponse({
                    'success': True,
                    'message': '已停止系统监控'
                })
            else:
                return JsonResponse({'error': '未知操作'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': '不支持的请求方法'}, status=405)
