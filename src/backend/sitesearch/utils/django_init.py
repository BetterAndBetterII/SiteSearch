import os
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))

import django
from django.conf import settings

# 设置Django环境
def init_django():
    # 设置Django设置模块
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'src.backend.sitesearch.conf.settings')
    
    # 如果没有完整的Django项目，可以手动配置设置
    if not settings.configured:
        settings.configure(
            DATABASES={
                'default': {
                    'ENGINE': 'django.db.backends.postgresql',  # 或其他数据库引擎
                    'NAME': os.getenv('DB_NAME'),
                    'USER': os.getenv('DB_USER'),
                    'PASSWORD': os.getenv('DB_PASSWORD'),
                    'HOST': os.getenv('DB_HOST'),
                    'PORT': os.getenv('DB_PORT'),
                }
            },
            INSTALLED_APPS=[
                'src.backend.sitesearch.storage',  # 包含models.py的应用
            ],
        )
    
    # 初始化Django
    django.setup()
