"""
URL配置
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.shortcuts import render
from django.views.static import serve
from django.conf import settings

def return_static(request, path, **kwargs):
    print(path)
    return serve(request, path, document_root=settings.STATICFILES_DIRS[0], **kwargs)

def index(request, path=''):
    return render(request, 'index.html')

urlpatterns = [
    re_path(r"^assets/(?P<path>.*)$", return_static, name="static"),  # 添加这行
    path('admin/', admin.site.urls),
    # API 路由
    path('api/', include('src.backend.sitesearch.api.urls')),
    # 托管静态文件
    path('', index),
    path('index.html', index),
    # 其余所有请求都返回index.html
    path('<path:path>', index),
] 