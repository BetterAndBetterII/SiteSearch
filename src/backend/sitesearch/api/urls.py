from django.urls import path

from src.backend.sitesearch.api.views import manage
from src.backend.sitesearch.api.views import sites
from src.backend.sitesearch.api.views import crawl_policies
from src.backend.sitesearch.api.views import documents
from src.backend.sitesearch.api.views import search
from src.backend.sitesearch.api.views import schedules
from src.backend.sitesearch.api.views import refresh_policies

# API 路由配置
urlpatterns = [
    # 系统状态管理
    path('health/', sites.health, name='health'),
    path('status/', manage.get_system_status, name='system_status'),
    path('workers/', manage.get_workers_count, name='workers_count'),
    path('queues/', manage.get_queue_metrics, name='all_queues'),
    path('queues/<str:queue_name>/', manage.get_queue_metrics, name='queue_metrics'),
    path('components/', manage.get_component_status, name='all_components'),
    path('components/<str:component_type>/', manage.get_component_status, name='component_status'),
    
    # 工作进程管理
    path('manage/components/', manage.manage_components, name='manage_components'),
    path('manage/scale/', manage.scale_workers, name='scale_workers'),
    path('manage/monitoring/', manage.toggle_monitoring, name='toggle_monitoring'),
    
    # 任务管理
    path('tasks/', manage.get_all_tasks, name='all_tasks'),
    path('tasks/create/', manage.create_task, name='create_task'),
    path('tasks/<str:task_id>/', manage.manage_task, name='manage_task'),
    
    # 站点管理
    path('sites/', sites.site_list, name='site_list'),
    path('sites/<str:site_id>/', sites.site_detail, name='site_detail'),
    path('sites/<str:site_id>/status/', sites.site_status, name='site_status'),
    path('sites/<str:site_id>/crawl-history/', sites.site_crawl_history, name='site_crawl_history'),
    
    # 爬取策略管理
    path('sites/<str:site_id>/crawl-policies/', crawl_policies.crawl_policy_list, name='crawl_policy_list'),
    path('sites/<str:site_id>/crawl-policies/<int:policy_id>/', crawl_policies.crawl_policy_detail, name='crawl_policy_detail'),
    path('sites/<str:site_id>/crawl-policies/<int:policy_id>/execute/', crawl_policies.execute_crawl_policy, name='execute_crawl_policy'),
    
    # 文档管理
    path('sites/<str:site_id>/documents/', documents.document_list, name='document_list'),
    path('sites/<str:site_id>/documents/<int:doc_id>/', documents.document_detail, name='document_detail'),
    path('sites/<str:site_id>/documents/<int:doc_id>/refresh/', documents.refresh_document, name='refresh_document'),
    # 文档列出，分页，排序，简单搜索；删除
    path('sites/<str:site_id>/documents/list/search/', documents.document_search, name='document_search'),
    path('sites/<str:site_id>/documents/list/delete/', documents.document_delete, name='document_delete'),
    path('documents/index/', documents.index_document, name='index_document'),
    
    # 搜索模块
    # path('search/', search.search, name='search'),
    path('semantic-search/', search.semantic_search, name='semantic_search'),
    path('chat/', search.chat, name='chat'),
    # path('search-feedback/<int:search_log_id>/', search.search_feedback, name='search_feedback'),
    
    # 定时任务模块
    path('check-policy-execution/', schedules.check_policy_execution, name='check_policy_execution'),
    path('sites/<str:site_id>/crawl-policies/<int:policy_id>/schedule/', schedules.create_schedule, name='create_schedule'),
    path('sites/<str:site_id>/schedules/', schedules.schedule_list, name='schedule_list'),
    path('sites/<str:site_id>/schedules/<int:schedule_id>/', schedules.schedule_detail, name='schedule_detail'),
    path('sites/<str:site_id>/schedules/<int:schedule_id>/toggle/', schedules.toggle_schedule, name='toggle_schedule'),
    
    # 内容刷新模块
    path('sites/<str:site_id>/refresh-policy/', refresh_policies.refresh_policy, name='refresh_policy'),
    path('sites/<str:site_id>/refresh/', refresh_policies.execute_refresh, name='execute_refresh'),
    
    # 系统管理模块
    path('system/stats/', manage.get_system_status, name='system_stats'),  # 复用系统状态接口
    path('system/workers/restart/', manage.manage_components, name='restart_workers'),  # 复用组件管理接口
    path('system/queue/<str:queue_name>/clear/', manage.get_queue_metrics, name='clear_queue'),  # 需要扩展队列接口以支持清空操作
] 