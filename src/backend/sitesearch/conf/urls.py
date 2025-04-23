"""
URL配置
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    # API 路由
    path('api/', include('src.backend.sitesearch.api.urls')),
] 