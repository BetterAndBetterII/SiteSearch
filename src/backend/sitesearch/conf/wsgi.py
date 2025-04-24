"""
WSGI配置
"""

import os
import multiprocessing

# 多进程支持
multiprocessing.set_start_method('spawn', force=True)

from django.core.wsgi import get_wsgi_application
import dotenv

dotenv.load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', '..', '.env'), override=True)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'src.backend.sitesearch.conf.settings')

application = get_wsgi_application() 