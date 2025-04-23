#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
import dotenv
from pathlib import Path

def main():
    """Run administrative tasks."""
    # 加载.env文件
    dotenv.load_dotenv(Path(__file__).resolve().parents[3] / '.env')
    
    # 设置Django设置模块
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'src.backend.sitesearch.conf.settings')
    
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    # 添加项目根目录到Python路径，确保导入能够正确工作
    project_root = Path(__file__).resolve().parents[3]  # 指向项目根目录
    sys.path.insert(0, str(project_root))
    
    main() 