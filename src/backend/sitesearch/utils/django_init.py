import os
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))

import django
from django.conf import settings

# 设置Django环境
def init_django():
    # 设置Django设置模块
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'src.backend.sitesearch.conf.settings')
    
    # 不要在这里调用 settings.configure() 来覆盖项目的设置，否则会导致 INSTALLED_APPS 缺失。
    # 只要确保 DJANGO_SETTINGS_MODULE 环境变量正确即可，django.setup() 会自动加载完整配置。
    
    # 初始化Django
    django.setup()
