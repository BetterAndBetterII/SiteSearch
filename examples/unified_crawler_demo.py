#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
统一爬虫系统示例脚本
演示如何使用爬虫管理器，支持HTTPX爬虫和Firecrawl爬虫
读取.env文件中的环境变量
"""

import os
import sys
import time
import logging
import argparse
import dotenv
from typing import Dict, Any, Optional

# 加载.env文件中的环境变量
dotenv.load_dotenv()

# 添加项目根目录到系统路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.backend.sitesearch.crawler.crawler_manager import CrawlerManager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('unified_crawler_demo.log')
    ]
)

logger = logging.getLogger('unified_crawler_demo')

def run_crawler(
    url: str, 
    crawler_id: str, 
    crawler_type: str = "httpx",
    max_urls: int = 10, 
    max_depth: int = 2, 
    delay: float = 0.5, 
    timeout: float = 30, 
    formats: list = None, 
    api_key: Optional[str] = None,
    api_endpoint: Optional[str] = None,
    wait: bool = True
) -> None:
    """
    运行爬虫示例
    
    Args:
        url: 要爬取的网站URL
        crawler_id: 爬虫ID
        crawler_type: 爬虫类型 ("httpx" 或 "firecrawl")
        max_urls: 最大爬取页面数
        max_depth: 最大爬取深度
        delay: 请求延迟(秒)
        timeout: 请求超时(秒)
        formats: 输出格式列表，默认为["markdown"]
        api_key: Firecrawl API密钥，默认从环境变量读取
        api_endpoint: Firecrawl API端点，默认从环境变量读取
        wait: 是否等待爬虫完成
    """
    # 创建存储目录
    storage_dir = f"./{crawler_type}_results"
    os.makedirs(storage_dir, exist_ok=True)
    
    # 创建爬虫管理器
    manager = CrawlerManager(storage_dir=storage_dir)
    
    # 检查爬虫类型
    if crawler_type not in ["httpx", "firecrawl"]:
        logger.error(f"不支持的爬虫类型: {crawler_type}。支持的类型为: httpx, firecrawl")
        return
    
    # 如果是firecrawl，检查API密钥
    if crawler_type == "firecrawl":
        api_key = api_key or os.environ.get("FIRECRAWL_API_KEY")
        api_endpoint = api_endpoint or os.environ.get("FIRECRAWL_API_ENDPOINT")
        
        if not api_key:
            logger.error("必须提供Firecrawl API密钥，通过--api-key参数或FIRECRAWL_API_KEY环境变量")
            return
    
    try:
        # 基础配置
        config = {
            "max_urls": max_urls,  # firecrawl
            "max_depth": max_depth,
            "headers": {
                "User-Agent": "SiteSearch-Crawler/1.0"
            },
        }
        
        # 根据爬虫类型添加特定配置
        if crawler_type == "httpx":
            config.update({
                "timeout": timeout,
            })
        elif crawler_type == "firecrawl":
            formats = formats or ["markdown"]
            config.update({
                "api_key": api_key,
                "formats": formats,
                "request_delay": delay,  # 为了避免速率限制
            })
        
        # 创建爬虫
        manager.create_crawler(
            crawler_id=crawler_id,
            crawler_type=crawler_type,
            base_url=url,
            config=config
        )
        
        logger.info(f"开始使用 {crawler_type} 爬取 {url}")
        
        # 启动爬虫
        manager.start_crawler(crawler_id, discover_sitemap=False)
        
        # 如果需要等待爬虫完成
        if wait:
            logger.info("等待爬虫完成...")
            check_interval = 5 if crawler_type == "firecrawl" else 2
            
            while True:
                status = manager.get_crawler_status(crawler_id)
                logger.info(f"状态: {status['status']}, "
                           f"已爬取: {status['stats'].get('pages_crawled', 0)}, "
                           f"失败: {status['stats'].get('pages_failed', 0)}")
                
                if status["status"] not in ["running", "created"]:
                    break
                    
                time.sleep(check_interval)
            
            # 爬取完成后的处理
            logger.info("爬取完成，保存结果...")
            
            # 保存结果
            result_file = manager.save_results(crawler_id)
            logger.info(f"结果已保存到: {result_file}")
        else:
            logger.info("爬虫已在后台启动，您可以稍后检查结果")
            
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在停止爬虫...")
        manager.stop_crawler(crawler_id)
        
    except Exception as e:
        logger.exception(f"爬取过程中发生错误: {str(e)}")
        
    finally:
        # 关闭管理器
        manager.close()
        logger.info("爬虫演示结束")

def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="统一爬虫演示脚本")
    parser.add_argument("url", help="要爬取的网站URL")
    parser.add_argument("--type", dest="crawler_type", choices=["httpx", "firecrawl"], default="httpx", 
                       help="爬虫类型: httpx或firecrawl")
    parser.add_argument("--id", dest="crawler_id", help="爬虫ID（默认基于时间和类型自动生成）")
    parser.add_argument("--max-urls", dest="max_urls", type=int, default=10, help="最大爬取页面数")
    parser.add_argument("--max-depth", dest="max_depth", type=int, default=2, help="最大爬取深度")
    parser.add_argument("--delay", type=float, default=0.5, help="请求延迟(秒)")
    parser.add_argument("--timeout", type=float, default=30, help="请求超时(秒)")
    parser.add_argument("--formats", nargs="+", default=["markdown"], 
                      choices=["markdown", "html", "text"], help="输出格式(仅firecrawl)")
    parser.add_argument("--api-key", help="Firecrawl API密钥(覆盖环境变量)")
    parser.add_argument("--api-endpoint", help="Firecrawl API端点(覆盖环境变量)")
    parser.add_argument("--no-wait", dest="wait", action="store_false", help="不等待爬虫完成")
    
    args = parser.parse_args()
    
    # 如果未指定爬虫ID，自动生成一个
    if not args.crawler_id:
        timestamp = int(time.time())
        args.crawler_id = f"{args.crawler_type}_{timestamp}"
    
    # 运行爬虫
    run_crawler(
        url=args.url,
        crawler_id=args.crawler_id,
        crawler_type=args.crawler_type,
        max_urls=args.max_urls,
        max_depth=args.max_depth,
        delay=args.delay,
        timeout=args.timeout,
        formats=args.formats,
        api_key=args.api_key,
        api_endpoint=args.api_endpoint,
        wait=args.wait
    )

if __name__ == "__main__":
    # python examples/unified_crawler_demo.py https://www.cuhk.edu.cn --type firecrawl --api-key fc-YOUR_API_KEY
    main() 